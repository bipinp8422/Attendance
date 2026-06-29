import streamlit as st
import pandas as pd
import io
import zipfile
import urllib.request
from datetime import datetime
from supabase import create_client, Client

# ────────────────────────────────────────────────
# Supabase settings
# Set these in Streamlit Cloud -> App settings -> Secrets:
#
# SUPABASE_URL = "https://xxxxxxxx.supabase.co"
# SUPABASE_KEY = "your-anon-key"
# ────────────────────────────────────────────────
SUPABASE_URL = "https://qhkpngsagsabtkcktroq.supabase.co"
SUPABASE_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFoa3BuZ3NhZ3NhYnRrY2t0cm9xIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODIzODE2MzMsImV4cCI6MjA5Nzk1NzYzM30.P_0gHBN_1UbNnlqur6m5NRS2s_GU6HJ4jmfIRD7gW24"


supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

ATT_TABLE = "attendance"
REQ_TABLE = "attendance_approval_requests"
USER_TABLE = "users"

REQUIRED_UPLOAD_COLS = {
    "store_region", "userid", "name", "userstatus",
    "doj", "tl_name", "bm_name", "date", "status"
}

# ────────────────────────────────────────────────
# Page config (must be first st call)
# ────────────────────────────────────────────────
st.set_page_config(
    page_title="Attendance Management",
    page_icon="🗓️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ────────────────────────────────────────────────
# Global styling
# ────────────────────────────────────────────────
st.markdown("""
<style>
    /* Overall page */
    .main { background-color: #f6f7fb; }

    /* Headings */
    h1, h2, h3 { font-weight: 700; }

    /* Card-like containers */
    .metric-card {
        background: #ffffff;
        border-radius: 14px;
        padding: 18px 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        border: 1px solid #eef0f5;
        text-align: center;
    }
    .metric-card .value {
        font-size: 28px;
        font-weight: 800;
        margin: 4px 0 0 0;
    }
    .metric-card .label {
        font-size: 13px;
        color: #6b7280;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }

    /* Login screen card */
    .login-card {
        background: #ffffff;
        border-radius: 16px;
        padding: 28px 26px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.07);
        border: 1px solid #eef0f5;
    }
    .login-banner {
        text-align: center;
        padding: 36px 0 18px 0;
    }
    .login-banner h1 {
        font-size: 34px;
        margin-bottom: 4px;
    }
    .login-banner p {
        color: #6b7280;
        font-size: 15px;
    }

    /* Buttons */
    div.stButton > button {
        border-radius: 10px;
        font-weight: 600;
        padding: 0.5rem 1.2rem;
    }
    div.stButton > button[kind="primary"] {
        background-color: #4f46e5;
        border: none;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #eef0f5;
    }

    /* Badge */
    .role-badge {
        display: inline-block;
        background: #eef2ff;
        color: #4338ca;
        font-weight: 600;
        font-size: 13px;
        padding: 4px 12px;
        border-radius: 999px;
        margin-bottom: 6px;
    }

    /* Expander tweak */
    div[data-testid="stExpander"] {
        border-radius: 12px !important;
        border: 1px solid #eef0f5 !important;
    }

    /* Pending badge */
    .pending-badge {
        display: inline-block;
        background: #fef3c7;
        color: #92400e;
        font-weight: 700;
        font-size: 13px;
        padding: 4px 12px;
        border-radius: 999px;
    }
</style>
""", unsafe_allow_html=True)

# ────────────────────────────────────────────────
# Session State
# ────────────────────────────────────────────────
st.session_state.setdefault("authenticated", False)
st.session_state.setdefault("role", None)
st.session_state.setdefault("username", None)

# ────────────────────────────────────────────────
# Login / Logout helpers
# ────────────────────────────────────────────────
def approval_login(role_required, icon):
    st.markdown(f"<div class='login-card'>", unsafe_allow_html=True)
    st.markdown(f"#### {icon} {role_required} Login")

    with st.form(f"{role_required}_login", border=False):
        u = st.text_input("Login ID", placeholder="Enter your login ID")
        p = st.text_input("Password", type="password", placeholder="Enter your password")
        submit = st.form_submit_button(f"Login as {role_required}", use_container_width=True, type="primary")

    st.markdown("</div>", unsafe_allow_html=True)

    if submit:
        if not u or not p:
            st.error("Please enter both Login ID and Password")
            return
        resp = (
            supabase.table(USER_TABLE)
            .select("*")
            .eq("username", u)
            .eq("password", p)
            .eq("role", role_required)
            .execute()
        )
        user_rows = resp.data

        if not user_rows:
            st.error("Invalid credentials")
        else:
            st.session_state.authenticated = True
            st.session_state.username = u
            st.session_state.role = role_required
            st.success(f"Logged in as {role_required}")
            st.rerun()

def logout():
    st.session_state.authenticated = False
    st.session_state.username = None
    st.session_state.role = None
    st.rerun()

# ────────────────────────────────────────────────
# Login Required Screen
# ────────────────────────────────────────────────
if not st.session_state.authenticated:
    st.markdown("""
    <div class="login-banner">
        <h1>🗓️ Attendance Management</h1>
        <p>Sign in as a Team Lead or Admin to view and manage attendance records.</p>
    </div>
    """, unsafe_allow_html=True)

    spacer_l, col1, col2, spacer_r = st.columns([1, 2, 2, 1])
    with col1:
        approval_login("TL", "🧑‍💼")
    with col2:
        approval_login("ADMIN", "🛡️")
    st.stop()

# ────────────────────────────────────────────────
# Load all attendance data (Supabase REST API, paginated)
# ────────────────────────────────────────────────
@st.cache_data(ttl=600)
def load_data():
    all_rows = []
    page_size = 1000
    start = 0
    while True:
        resp = (
            supabase.table(ATT_TABLE)
            .select("store_region, userid, name, userstatus, doj, tl_name, bm_name, date, status")
            .range(start, start + page_size - 1)
            .execute()
        )
        rows = resp.data
        if not rows:
            break
        all_rows.extend(rows)
        if len(rows) < page_size:
            break
        start += page_size

    df = pd.DataFrame(all_rows)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    df["doj"] = pd.to_datetime(df["doj"])
    df = df.sort_values(["userid", "date"]).reset_index(drop=True)
    return df


# ────────────────────────────────────────────────
# Pending attachment helper
# Treats a request as "pending" if it has no usable
# attachment URL (e.g. upload failed, or it was never
# attached). Since changes auto-approve, this is the
# main thing left to chase down.
# ────────────────────────────────────────────────
@st.cache_data(ttl=120)
def load_pending_attachment_count(username=None, role=None):
    resp = supabase.table(REQ_TABLE).select("id, attachment_url, level1_by").execute()
    rows = resp.data or []
    if role == "TL" and username:
        rows = [r for r in rows if r.get("level1_by") == username]
    pending = [
        r for r in rows
        if not r.get("attachment_url") or not str(r.get("attachment_url")).strip().startswith("http")
    ]
    return len(pending)


# ────────────────────────────────────────────────
# Load approval-request records (used to know which
# leave dates already have a valid mail attachment).
# ────────────────────────────────────────────────
@st.cache_data(ttl=120)
def load_requests():
    resp = (
        supabase.table(REQ_TABLE)
        .select("userid, att_date, new_status, attachment_url")
        .execute()
    )
    rows = resp.data or []
    rdf = pd.DataFrame(rows, columns=["userid", "att_date", "new_status", "attachment_url"])
    return rdf


df = load_data()

if df.empty:
    st.warning("No attendance data found.")
    st.stop()

# ────────────────────────────────────────────────
# Header
# ────────────────────────────────────────────────
role_icon = {"TL": "🧑‍💼", "ADMIN": "🛡️"}.get(st.session_state.role, "👤")
header_l, header_r = st.columns([5, 1])
with header_l:
    st.markdown(f"<span class='role-badge'>{role_icon} {st.session_state.role}</span>", unsafe_allow_html=True)
    if st.session_state.role == "TL":
        st.title(f"Team Attendance – {st.session_state.username}")
        st.caption("View and directly update your assigned employees' attendance. An attachment is required for every change.")
    else:
        st.title(f"Admin Console – {st.session_state.username}")
        st.caption("Upload monthly attendance, view all records, and download approval attachments across the organization.")
with header_r:
    st.write("")
    if st.button("🚪 Logout", use_container_width=True):
        logout()

# Pending attachments banner (org-wide for admin, own submissions for TL)
pending_count = load_pending_attachment_count(
    username=st.session_state.username,
    role=st.session_state.role,
)
if pending_count > 0:
    label = "across the organization" if st.session_state.role == "ADMIN" else "from your submissions"
    st.markdown(
        f"<span class='pending-badge'>⏳ {pending_count} leave/change record(s) {label} are missing a valid attachment</span>",
        unsafe_allow_html=True,
    )
    st.write("")

# ────────────────────────────────────────────────
# Get dynamic filter options
# ────────────────────────────────────────────────
region_options = sorted(df["store_region"].dropna().unique().tolist())
status_options = sorted(df["status"].dropna().unique().tolist())

# ────────────────────────────────────────────────
# Sidebar filters
# ────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"### 👋 {st.session_state.username}")
    st.caption(f"Logged in as **{st.session_state.role}**")

    pc1, pc2 = st.columns(2)
    with pc1:
        st.metric("⏳ Pending Attachments", pending_count)
    st.divider()

    st.markdown("#### 🔍 Filters")
    region_filter = st.multiselect("Region", region_options, placeholder="All regions")
    status_filter = st.multiselect("Status", status_options, placeholder="All statuses")

    col1, col2 = st.columns(2)
    with col1:
        date_from = st.date_input("From date", value=None)
    with col2:
        date_to = st.date_input("To date", value=None)

    st.divider()
    edit_mode = False
    if st.session_state.role == "TL":
        edit_mode = st.toggle("✏️ Enable editing", value=False)

    st.divider()
    if st.button("🔄 Reload Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ────────────────────────────────────────────────
# Apply filters
# ────────────────────────────────────────────────
filtered = df.copy()

if region_filter:
    filtered = filtered[filtered["store_region"].isin(region_filter)]
if status_filter:
    filtered = filtered[filtered["status"].isin(status_filter)]
if date_from:
    filtered = filtered[filtered["date"] >= pd.to_datetime(date_from)]
if date_to:
    filtered = filtered[filtered["date"] <= pd.to_datetime(date_to)]

if st.session_state.role == "TL":
    filtered = filtered[filtered["tl_name"] == st.session_state.username]

if filtered.empty:
    st.warning("No data after applying filters or no employees assigned to you.")
    st.stop()

# ────────────────────────────────────────────────
# Summary metric cards
# ────────────────────────────────────────────────
total_employees = filtered["userid"].nunique()
latest_date = filtered["date"].max()
latest_day_df = filtered[filtered["date"] == latest_date]
present_today = (latest_day_df["status"] == "P").sum()
absent_today = (latest_day_df["status"] == "A").sum()
leave_today = latest_day_df["status"].isin(["L", "H", "WO"]).sum()

m1, m2, m3, m4 = st.columns(4)
metrics = [
    (m1, "👥 Employees", total_employees),
    (m2, "✅ Present Today", present_today),
    (m3, "❌ Absent Today", absent_today),
    (m4, "🌴 Leave / Off Today", leave_today),
]
for col, label, value in metrics:
    with col:
        st.markdown(f"""
        <div class="metric-card">
            <div class="label">{label}</div>
            <div class="value">{value}</div>
        </div>
        """, unsafe_allow_html=True)

st.write("")

# ────────────────────────────────────────────────
# Pivot
# ────────────────────────────────────────────────
pivot = filtered.pivot_table(
    index=["store_region", "userid", "name", "userstatus", "doj", "tl_name", "bm_name"],
    columns="date",
    values="status",
    aggfunc="first"
).reset_index()

pivot = pivot.sort_values(["store_region", "name"]).reset_index(drop=True)

display_pivot = pivot.copy()
display_pivot["doj"] = display_pivot["doj"].dt.strftime("%d-%m-%Y")

display_pivot.columns = [
    c.strftime("%d-%m-%Y") if isinstance(c, pd.Timestamp) else c
    for c in display_pivot.columns
]

date_columns = [
    c for c in display_pivot.columns
    if c not in ["store_region", "userid", "name", "userstatus", "doj", "tl_name", "bm_name"]
]

# ────────────────────────────────────────────────
# Leave / absence summary (per employee, over filtered range)
# ────────────────────────────────────────────────
STATUS_LABELS = {
    "P": "Present",
    "A": "Absent",
    "L": "Leave",
    "H": "Holiday",
    "WO": "Week Off",
}

def build_leave_summary(data: pd.DataFrame) -> pd.DataFrame:
    counts = (
        data.groupby(["store_region", "userid", "name", "tl_name"])["status"]
        .value_counts()
        .unstack(fill_value=0)
        .reset_index()
    )
    for code in ["P", "A", "L", "H", "WO"]:
        if code not in counts.columns:
            counts[code] = 0
    counts = counts.rename(columns=STATUS_LABELS)
    counts["Total Days"] = counts[list(STATUS_LABELS.values())].sum(axis=1)
    counts = counts.sort_values("Absent" if "Absent" in counts.columns else "name", ascending=False)
    return counts

leave_summary = build_leave_summary(filtered)

# ────────────────────────────────────────────────
# Leave-date level mail tracking
# Cross-reference each individual leave (status == "L")
# date against attendance_approval_requests to see
# whether a valid approval-mail attachment was received
# for that exact userid + date.
# ────────────────────────────────────────────────
requests_df = load_requests()

leave_rows = filtered[filtered["status"] == "L"].copy()
leave_rows["date_iso"] = leave_rows["date"].dt.strftime("%Y-%m-%d")
leave_rows["date_disp"] = leave_rows["date"].dt.strftime("%d-%b-%y")

mail_received_keys = set()
if not requests_df.empty:
    valid_mail = requests_df[
        (requests_df["new_status"] == "L")
        & requests_df["attachment_url"].astype(str).str.strip().str.startswith("http")
    ]
    mail_received_keys = set(zip(valid_mail["userid"], valid_mail["att_date"]))

leave_rows["mail_status"] = leave_rows.apply(
    lambda r: "✅" if (r["userid"], r["date_iso"]) in mail_received_keys else "⏳",
    axis=1,
)

# Roll mail counts up into the per-employee leave summary
if not leave_rows.empty:
    mail_counts = (
        leave_rows.groupby("userid")["mail_status"]
        .apply(lambda s: (s == "✅").sum())
        .rename("Leave Mails Received")
        .reset_index()
    )
    leave_summary = leave_summary.merge(mail_counts, on="userid", how="left")
else:
    leave_summary["Leave Mails Received"] = 0

leave_summary["Leave Mails Received"] = leave_summary["Leave Mails Received"].fillna(0).astype(int)
leave_col = "Leave" if "Leave" in leave_summary.columns else None
if leave_col:
    leave_summary["Leave Mails Pending"] = (leave_summary[leave_col] - leave_summary["Leave Mails Received"]).clip(lower=0)

# ────────────────────────────────────────────────
# Conditional formatting
# ────────────────────────────────────────────────
def color_status(val):
    colors = {
        "P": "background-color: #d1fae5; color: #065f46; font-weight:600;",
        "A": "background-color: #fee2e2; color: #991b1b; font-weight:600;",
        "L": "background-color: #fed7aa; color: #92400e; font-weight:600;",
        "H": "background-color: #fef3c7; color: #92400e; font-weight:600;",
        "WO": "background-color: #fef3c7; color: #92400e; font-weight:600;",
    }
    return colors.get(val, "background-color: #f3f4f6; color: #6b7280;")

pinned_cols = ["store_region", "userid", "name", "userstatus", "doj", "tl_name", "bm_name"]

# ────────────────────────────────────────────────
# Tabs
# Admin: Table | Leave Summary | Upload Attendance | Change Records | Export
# TL:    Table | Leave Summary | Export
# ────────────────────────────────────────────────
if st.session_state.role == "ADMIN":
    tab_table, tab_leave, tab_upload, tab_admin, tab_export = st.tabs(
        ["📋 Attendance Table", "📊 Leave Summary", "📤 Upload Attendance", "🛡️ Change Records & Attachments", "⬇️ Export"]
    )
else:
    tab_table, tab_leave, tab_export = st.tabs(["📋 Attendance Table", "📊 Leave Summary", "⬇️ Export"])
    tab_admin = None
    tab_upload = None

# ───── TAB: Attendance Table ─────
with tab_table:
    if edit_mode:
        st.info("✏️ Edit mode is on — change a cell's status, then submit/save below.", icon="✏️")

        column_config = {c: st.column_config.TextColumn(disabled=True, pinned=True) for c in pinned_cols}
        for col in date_columns:
            column_config[col] = st.column_config.SelectboxColumn(
                options=["", "P", "A", "L", "H", "WO"],
                required=False
            )

        edited_df = st.data_editor(
            display_pivot,
            column_config=column_config,
            use_container_width=True,
            height=600,
            hide_index=True,
            num_rows="fixed"
        )

        st.divider()

        if st.session_state.role == "TL":
            st.markdown("##### 📨 Apply attendance changes")

            # Build list of individual changes (row, date)
            pending_changes = []
            for i in range(len(edited_df)):
                for d in date_columns:
                    old = display_pivot.iloc[i][d]
                    new = edited_df.iloc[i][d]
                    old_val = None if pd.isna(old) or old == "" else old
                    new_val = None if pd.isna(new) or new == "" else new
                    if old_val != new_val:
                        pending_changes.append({
                            "row": i,
                            "date": d,
                            "userid": edited_df.iloc[i]["userid"],
                            "name": edited_df.iloc[i]["name"],
                            "old": old_val,
                            "new": new_val,
                        })

            if not pending_changes:
                st.info("No changes detected yet. Edit a date's status above to begin.")
            else:
                st.warning(
                    f"📎 You changed {len(pending_changes)} date(s). "
                    "Each change below requires its own attachment (approval proof) before you can apply it. "
                    "Changes to Leave (L) must include the leave-approval mail/screenshot as the attachment."
                )

                remark = st.text_area("✍️ Overall remark (mandatory)", placeholder="Explain the reason for these changes...")

                st.markdown("###### Per-change attachments")
                change_attachments = {}
                all_attached = True
                for idx, chg in enumerate(pending_changes):
                    with st.container(border=True):
                        c1, c2 = st.columns([2, 2])
                        with c1:
                            is_leave = chg["new"] == "L"
                            label = "📩 Leave (mail attachment required)" if is_leave else f"📅 {chg['date']}"
                            st.markdown(
                                f"**{chg['name']}** ({chg['userid']})  \n"
                                f"{label}: `{chg['old'] or '—'}` → `{chg['new'] or '—'}`"
                            )
                        with c2:
                            file = st.file_uploader(
                                "📎 Attachment (required)" + (" — leave approval mail" if chg["new"] == "L" else ""),
                                type=["png", "jpg", "jpeg", "pdf", "eml", "msg"],
                                key=f"attach_{idx}_{chg['userid']}_{chg['date']}"
                            )
                            change_attachments[idx] = file
                            if file is None:
                                all_attached = False

                if st.button("✅ Apply Changes", type="primary"):
                    if not remark.strip():
                        st.error("Overall remark is mandatory")
                    elif not all_attached:
                        st.error("📎 Every changed date requires its own attachment before applying.")
                    else:
                        with st.spinner("Uploading attachments and applying changes..."):
                            for idx, chg in enumerate(pending_changes):
                                file = change_attachments[idx]
                                file_bytes = file.getvalue()
                                file_ext = file.name.split(".")[-1]
                                storage_path = (
                                    f"{st.session_state.username}_{chg['userid']}_"
                                    f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{idx}.{file_ext}"
                                )
                                try:
                                    supabase.storage.from_("approval-attachments").upload(
                                        storage_path, file_bytes, {"content-type": file.type}
                                    )
                                    attachment_url = supabase.storage.from_(
                                        "approval-attachments"
                                    ).get_public_url(storage_path)
                                except Exception as e:
                                    st.error(f"Attachment upload failed for {chg['userid']} / {chg['date']}: {e}")
                                    st.stop()

                                att_date_iso = datetime.strptime(chg["date"], "%d-%m-%Y").date().isoformat()

                                # Apply the change directly to attendance — no approver needed
                                supabase.table(ATT_TABLE).update(
                                    {"status": chg["new"]}
                                ).eq("userid", chg["userid"]).eq("date", att_date_iso).execute()

                                # Log it for Admin's audit trail
                                supabase.table(REQ_TABLE).insert({
                                    "userid": chg["userid"],
                                    "att_date": att_date_iso,
                                    "old_status": chg["old"],
                                    "new_status": chg["new"],
                                    "remark": remark,
                                    "attachment_url": attachment_url,
                                    "level1_by": st.session_state.username,
                                    "level1_at": datetime.utcnow().isoformat(),
                                    "level1_status": "APPROVED",
                                    "level2_status": "APPROVED",
                                    "level2_by": "AUTO (no approver required)",
                                    "level2_at": datetime.utcnow().isoformat(),
                                }).execute()

                        st.success("Changes applied directly to attendance records ✅")
                        st.cache_data.clear()
                        st.rerun()
    else:
        styled = display_pivot.style.map(color_status, subset=date_columns)
        st.dataframe(
            styled,
            use_container_width=True,
            height=600,
            hide_index=True,
            column_config={c: st.column_config.TextColumn(pinned=True) for c in pinned_cols}
        )

# ───── TAB: Leave Summary ─────
with tab_leave:
    st.markdown("##### 📊 Leave & Absence Summary")
    st.caption("Per-employee counts of Present / Absent / Leave / Holiday / Week-off for the dates currently selected in the sidebar filters.")

    s1, s2, s3, s4 = st.columns(4)
    with s1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="label">Total Absent Days</div>
            <div class="value">{int(leave_summary["Absent"].sum())}</div>
        </div>
        """, unsafe_allow_html=True)
    with s2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="label">Total Leave Days</div>
            <div class="value">{int(leave_summary["Leave"].sum())}</div>
        </div>
        """, unsafe_allow_html=True)
    with s3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="label">Employees with ≥1 Absence</div>
            <div class="value">{int((leave_summary["Absent"] > 0).sum())}</div>
        </div>
        """, unsafe_allow_html=True)
    with s4:
        pending_mails = int(leave_summary["Leave Mails Pending"].sum()) if "Leave Mails Pending" in leave_summary.columns else 0
        st.markdown(f"""
        <div class="metric-card">
            <div class="label">Leave Mails Pending</div>
            <div class="value">{pending_mails}</div>
        </div>
        """, unsafe_allow_html=True)

    st.write("")
    st.dataframe(
        leave_summary,
        use_container_width=True,
        hide_index=True,
        height=520,
    )

    st.download_button(
        "⬇️ Download Leave Summary as CSV",
        leave_summary.to_csv(index=False).encode("utf-8"),
        f"leave_summary_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
    )

    st.divider()
    st.markdown("##### 📨 Leave Approval Mail Tracker")
    st.caption(
        "Date-wise view of every leave (L) taken in the selected range, and whether a valid "
        "approval-mail attachment has been received for that specific date. "
        "✅ = mail received · ⏳ = mail missing/pending."
    )

    if leave_rows.empty:
        st.info("No leave (L) days in the currently selected filters.")
    else:
        # Keep leave dates in chronological order across columns
        ordered_dates = (
            leave_rows[["date", "date_disp"]]
            .drop_duplicates()
            .sort_values("date")["date_disp"]
            .tolist()
        )

        tracker_pivot = leave_rows.pivot_table(
            index=["store_region", "userid", "name", "tl_name"],
            columns="date_disp",
            values="mail_status",
            aggfunc="first",
        ).reset_index()

        # Reorder date columns chronologically
        fixed_cols = ["store_region", "userid", "name", "tl_name"]
        tracker_pivot = tracker_pivot[fixed_cols + [d for d in ordered_dates if d in tracker_pivot.columns]]
        tracker_pivot = tracker_pivot.sort_values(["store_region", "name"]).reset_index(drop=True)

        mail_date_cols = [c for c in tracker_pivot.columns if c not in fixed_cols]

        def color_mail(val):
            if val == "✅":
                return "background-color: #d1fae5; color: #065f46; font-weight:600;"
            if val == "⏳":
                return "background-color: #fee2e2; color: #991b1b; font-weight:600;"
            return "background-color: #f3f4f6; color: #6b7280;"

        styled_tracker = tracker_pivot.style.map(color_mail, subset=mail_date_cols)
        st.dataframe(
            styled_tracker,
            use_container_width=True,
            hide_index=True,
            height=420,
            column_config={c: st.column_config.TextColumn(pinned=True) for c in fixed_cols},
        )

        st.download_button(
            "⬇️ Download Mail Tracker as CSV",
            tracker_pivot.to_csv(index=False).encode("utf-8"),
            f"leave_mail_tracker_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
        )


# ───── TAB: Admin - Upload Monthly Attendance ─────
if tab_upload is not None:
    with tab_upload:
        st.markdown("##### 📤 Upload Monthly Attendance")
        st.caption(
            "Upload a CSV or Excel file with one row per employee per day. "
            "Required columns: " + ", ".join(sorted(REQUIRED_UPLOAD_COLS)) + ". "
            "Rows for an existing userid + date will overwrite the existing record."
        )

        st.info(
            "💡 For overwrite-on-upload to work, the `attendance` table needs a unique "
            "constraint on (userid, date). If it doesn't have one yet, ask your DB admin to add it — "
            "otherwise duplicate rows may be created instead of updated.",
            icon="💡",
        )

        upload_file = st.file_uploader("Choose attendance file", type=["csv", "xlsx"], key="monthly_upload")

        if upload_file is not None:
            try:
                if upload_file.name.lower().endswith(".csv"):
                    new_df = pd.read_csv(upload_file)
                else:
                    new_df = pd.read_excel(upload_file)
            except Exception as e:
                st.error(f"Could not read file: {e}")
                st.stop()

            new_df.columns = [str(c).strip().lower() for c in new_df.columns]
            missing_cols = REQUIRED_UPLOAD_COLS - set(new_df.columns)

            if missing_cols:
                st.error(f"File is missing required column(s): {', '.join(sorted(missing_cols))}")
            else:
                try:
                    new_df["date"] = pd.to_datetime(new_df["date"]).dt.strftime("%Y-%m-%d")
                    new_df["doj"] = pd.to_datetime(new_df["doj"]).dt.strftime("%Y-%m-%d")
                except Exception as e:
                    st.error(f"Could not parse date/doj columns: {e}")
                    st.stop()

                new_df = new_df[list(REQUIRED_UPLOAD_COLS)]

                st.markdown(f"**Preview** — {len(new_df)} row(s) detected")
                st.dataframe(new_df.head(20), use_container_width=True, hide_index=True)

                confirm = st.checkbox("I've checked the preview and want to upload these records")
                if st.button("✅ Confirm Upload", type="primary", disabled=not confirm):
                    records = new_df.to_dict("records")
                    batch_size = 500
                    errors = []
                    with st.spinner(f"Uploading {len(records)} row(s)..."):
                        for i in range(0, len(records), batch_size):
                            chunk = records[i:i + batch_size]
                            try:
                                supabase.table(ATT_TABLE).upsert(chunk, on_conflict="userid,date").execute()
                            except Exception as e:
                                errors.append(str(e))

                    if errors:
                        st.error("Some batches failed to upload:\n" + "\n".join(errors[:5]))
                    else:
                        st.success(f"Uploaded {len(records)} row(s) successfully ✅")
                        st.cache_data.clear()
                        st.rerun()

# ───── TAB: Admin - Approval Records & Attachments ─────
if tab_admin is not None:
    with tab_admin:
        resp = (
            supabase.table(REQ_TABLE)
            .select("*")
            .order("level1_at", desc=True)
            .execute()
        )
        all_reqs = pd.DataFrame(resp.data)

        if all_reqs.empty:
            st.info("No approval requests have been submitted yet.")
        else:
            st.caption(f"{len(all_reqs)} total approval record(s)")

            status_pick = st.multiselect(
                "Filter by final status",
                options=sorted(all_reqs["level2_status"].dropna().unique().tolist()),
                placeholder="All statuses"
            )
            view_df = all_reqs.copy()
            if status_pick:
                view_df = view_df[view_df["level2_status"].isin(status_pick)]

            # Lookup employee names from attendance data by userid
            name_lookup = df.drop_duplicates("userid").set_index("userid")["name"].to_dict()

            def safe_filename(name, userid, att_date, ext):
                clean_name = "".join(c for c in str(name) if c.isalnum() or c in (" ", "_")).strip().replace(" ", "_")
                return f"{clean_name}_{userid}_{att_date}.{ext}"

            st.markdown("###### Records")
            for idx, r in view_df.iterrows():
                emp_name = name_lookup.get(r.userid, r.userid)
                has_attachment = r.get("attachment_url") and str(r.get("attachment_url")).strip().startswith("http")
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 2, 2])
                    with c1:
                        st.markdown(f"**{emp_name}** ({r.userid})")
                        st.caption(f"{r.att_date}  |  {r.old_status or '—'} → {r.new_status or '—'}")
                        st.caption(f"Remark: {r.remark or '—'}")
                        if not has_attachment:
                            st.caption("⏳ Pending — no valid attachment")
                    with c2:
                        st.caption(f"Requested by: {r.level1_by}")
                        st.caption(f"Final status: **{r.level2_status or 'PENDING'}**")
                    with c3:
                        att_url = r.get("attachment_url")
                        if has_attachment:
                            try:
                                file_bytes = urllib.request.urlopen(att_url, timeout=10).read()
                                ext = att_url.split(".")[-1].split("?")[0]
                                fname = safe_filename(emp_name, r.userid, r.att_date, ext)
                                st.download_button(
                                    "⬇️ Download",
                                    data=file_bytes,
                                    file_name=fname,
                                    key=f"dl_{r.id}_{idx}",
                                    use_container_width=True
                                )
                            except Exception:
                                st.caption("⚠️ Attachment missing or broken (likely a failed old upload)")
                        else:
                            st.caption("No attachment")

            st.divider()
            st.markdown("###### Bulk download")
            st.caption("Download every attachment in the filtered list above as a single ZIP, each file named EmployeeName_UserID_Date.")

            if st.button("📦 Download All as ZIP", type="primary"):
                rows_with_files = [
                    r for _, r in view_df.iterrows()
                    if r.get("attachment_url") and not pd.isna(r.get("attachment_url"))
                    and str(r.get("attachment_url")).strip().startswith("http")
                ]
                if not rows_with_files:
                    st.warning("No attachments found in the current filtered view.")
                else:
                    with st.spinner(f"Packaging {len(rows_with_files)} file(s)..."):
                        zip_buffer = io.BytesIO()
                        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                            for r in rows_with_files:
                                emp_name = name_lookup.get(r.userid, r.userid)
                                try:
                                    file_bytes = urllib.request.urlopen(r.attachment_url, timeout=10).read()
                                    ext = r.attachment_url.split(".")[-1].split("?")[0]
                                    fname = safe_filename(emp_name, r.userid, r.att_date, ext)
                                    zf.writestr(fname, file_bytes)
                                except Exception:
                                    continue
                        zip_buffer.seek(0)

                    st.download_button(
                        "⬇️ Click to save ZIP",
                        data=zip_buffer,
                        file_name=f"attendance_attachments_{datetime.now().strftime('%Y%m%d_%H%M')}.zip",
                        mime="application/zip",
                        type="primary"
                    )

# ───── TAB: Export ─────
with tab_export:
    st.markdown("##### ⬇️ Download current filtered view")
    st.caption("Exports exactly what's shown in the Attendance Table tab, based on your active filters.")
    st.download_button(
        "Download as CSV",
        display_pivot.to_csv(index=False).encode("utf-8"),
        f"attendance_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
        type="primary"
    )

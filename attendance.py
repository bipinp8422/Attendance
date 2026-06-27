import streamlit as st
import pandas as pd
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
        <p>Sign in as a Team Lead or Branch Manager to view and manage attendance records.</p>
    </div>
    """, unsafe_allow_html=True)

    spacer_l, col1, col2, spacer_r = st.columns([1, 2, 2, 1])
    with col1:
        approval_login("TL", "🧑‍💼")
    with col2:
        approval_login("BM", "🏢")
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

df = load_data()

if df.empty:
    st.warning("No attendance data found.")
    st.stop()

# ────────────────────────────────────────────────
# Header
# ────────────────────────────────────────────────
role_icon = "🧑‍💼" if st.session_state.role == "TL" else "🏢"
header_l, header_r = st.columns([5, 1])
with header_l:
    st.markdown(f"<span class='role-badge'>{role_icon} {st.session_state.role}</span>", unsafe_allow_html=True)
    if st.session_state.role == "TL":
        st.title(f"Team Attendance – {st.session_state.username}")
        st.caption("View your assigned employees' attendance. Edits require BM approval.")
    else:
        st.title(f"Branch Attendance – {st.session_state.username}")
        st.caption("View your assigned branch/region employees. Edit directly or approve TL requests.")
with header_r:
    st.write("")
    if st.button("🚪 Logout", use_container_width=True):
        logout()

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
    if st.session_state.role in ["TL", "BM"]:
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
elif st.session_state.role == "BM":
    filtered = filtered[filtered["bm_name"] == st.session_state.username]

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
# Tabs: Attendance Table | Approvals (BM only) | Export
# ────────────────────────────────────────────────
if st.session_state.role == "BM":
    tab_table, tab_approvals, tab_export = st.tabs(["📋 Attendance Table", "🔵 Approval Requests", "⬇️ Export"])
else:
    tab_table, tab_export = st.tabs(["📋 Attendance Table", "⬇️ Export"])
    tab_approvals = None

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
            st.markdown("##### 📨 Submit changes for BM approval")
            remark = st.text_area("✍️ Remark (mandatory)", placeholder="Explain the reason for this change...")
            attachment = st.file_uploader(
                "📎 Attach approval proof (screenshot/PDF of approval email) — optional",
                type=["png", "jpg", "jpeg", "pdf"]
            )

            if st.button("Submit Changes for BM Approval", type="primary"):
                if not remark.strip():
                    st.error("Remark is mandatory")
                else:
                    attachment_url = None
                    if attachment is not None:
                        file_bytes = attachment.getvalue()
                        file_ext = attachment.name.split(".")[-1]
                        storage_path = (
                            f"{st.session_state.username}_"
                            f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.{file_ext}"
                        )
                        try:
                            supabase.storage.from_("approval-attachments").upload(
                                storage_path, file_bytes, {"content-type": attachment.type}
                            )
                            attachment_url = supabase.storage.from_(
                                "approval-attachments"
                            ).get_public_url(storage_path)
                        except Exception as e:
                            st.error(f"Attachment upload failed: {e}")
                            st.stop()

                    changes_made = False
                    with st.spinner("Submitting changes..."):
                        for i in range(len(edited_df)):
                            for d in date_columns:
                                old = display_pivot.iloc[i][d]
                                new = edited_df.iloc[i][d]
                                old_val = None if pd.isna(old) or old == "" else old
                                new_val = None if pd.isna(new) or new == "" else new
                                if old_val == new_val:
                                    continue
                                changes_made = True
                                supabase.table(REQ_TABLE).insert({
                                    "userid": edited_df.iloc[i]["userid"],
                                    "att_date": datetime.strptime(d, "%d-%m-%Y").date().isoformat(),
                                    "old_status": old_val,
                                    "new_status": new_val,
                                    "remark": remark,
                                    "attachment_url": attachment_url,
                                    "level1_by": st.session_state.username,
                                    "level1_at": datetime.utcnow().isoformat(),
                                    "level1_status": "APPROVED",
                                }).execute()

                    if changes_made:
                        st.success("Changes submitted for BM approval ✅")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.info("No changes detected — nothing submitted.")

        elif st.session_state.role == "BM":
            if st.button("💾 Save Changes Directly", type="primary"):
                changes_made = False
                with st.spinner("Saving changes..."):
                    for i in range(len(edited_df)):
                        for d in date_columns:
                            old = display_pivot.iloc[i][d]
                            new = edited_df.iloc[i][d]
                            old_val = None if pd.isna(old) or old == "" else old
                            new_val = None if pd.isna(new) or new == "" else new
                            if old_val == new_val:
                                continue
                            changes_made = True
                            supabase.table(ATT_TABLE).update(
                                {"status": new_val}
                            ).eq("userid", edited_df.iloc[i]["userid"]).eq(
                                "date", datetime.strptime(d, "%d-%m-%Y").date().isoformat()
                            ).execute()

                if changes_made:
                    st.success("Changes saved directly to the database ✅")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.info("No changes detected — nothing saved.")

    else:
        styled = display_pivot.style.map(color_status, subset=date_columns)
        st.dataframe(
            styled,
            use_container_width=True,
            height=600,
            hide_index=True,
            column_config={c: st.column_config.TextColumn(pinned=True) for c in pinned_cols}
        )

# ───── TAB: Approvals (BM only) ─────
if tab_approvals is not None:
    with tab_approvals:
        resp = (
            supabase.table(REQ_TABLE)
            .select("*")
            .eq("level1_status", "APPROVED")
            .eq("level2_status", "PENDING")
            .order("level1_at", desc=True)
            .execute()
        )
        reqs = pd.DataFrame(resp.data)

        if reqs.empty:
            st.success("🎉 No pending approval requests — you're all caught up!")
        else:
            st.caption(f"{len(reqs)} request(s) awaiting your review")
            for idx, r in reqs.iterrows():
                with st.expander(
                    f"🧾 {r['name'] if 'name' in r and pd.notna(r.get('name')) else r.userid}  |  "
                    f"{r.att_date}  |  {r.old_status or '—'} → {r.new_status or '—'}  (Req #{r.id})"
                ):
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.markdown(f"**Remark:** {r.remark}")
                        st.caption(f"Requested by {r.level1_by} on {r.level1_at}")
                        if r.get("attachment_url"):
                            st.markdown(f"📎 [View attached proof]({r.attachment_url})")

                    bcol1, bcol2 = st.columns(2)
                    if bcol1.button("✅ Approve", key=f"approve_{r.id}_{idx}", use_container_width=True, type="primary"):
                        supabase.table(ATT_TABLE).update(
                            {"status": r.new_status}
                        ).eq("userid", r.userid).eq("date", r.att_date).execute()

                        supabase.table(REQ_TABLE).update({
                            "level2_status": "APPROVED",
                            "level2_by": st.session_state.username,
                            "level2_at": datetime.utcnow().isoformat(),
                        }).eq("id", r.id).execute()

                        st.success(f"Request {r.id} approved")
                        st.cache_data.clear()
                        st.rerun()

                    if bcol2.button("❌ Reject", key=f"reject_{r.id}_{idx}", use_container_width=True):
                        supabase.table(REQ_TABLE).update({
                            "level2_status": "REJECTED",
                            "level2_by": st.session_state.username,
                            "level2_at": datetime.utcnow().isoformat(),
                        }).eq("id", r.id).execute()

                        st.warning(f"Request {r.id} rejected")
                        st.cache_data.clear()
                        st.rerun()

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

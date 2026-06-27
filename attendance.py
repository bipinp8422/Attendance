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
#
# IMPORTANT: Make sure Row Level Security (RLS) is enabled on
# users / attendance / attendance_approval_requests tables with
# appropriate policies, since the anon key is exposed client-side.
# ────────────────────────────────────────────────
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

ATT_TABLE = "attendance"
REQ_TABLE = "attendance_approval_requests"
USER_TABLE = "users"

# ────────────────────────────────────────────────
# Session State
# ────────────────────────────────────────────────
st.session_state.setdefault("authenticated", False)
st.session_state.setdefault("role", None)
st.session_state.setdefault("username", None)

# ────────────────────────────────────────────────
# Login / Logout helpers (defined FIRST)
# ────────────────────────────────────────────────
def approval_login(role_required):
    st.warning(f"🔐 {role_required} login required")

    with st.form(f"{role_required}_login"):
        u = st.text_input("Login ID")
        p = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")

    if submit:
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
    st.success("Logged out")
    st.rerun()

# ────────────────────────────────────────────────
# Page config
# ────────────────────────────────────────────────
st.set_page_config(page_title="Attendance Management", layout="wide")

# ────────────────────────────────────────────────
# Login Required Check
# ────────────────────────────────────────────────
if not st.session_state.authenticated:
    st.title("Login Required")
    st.markdown("Please login as TL or BM to view attendance records.")

    col1, col2 = st.columns(2)
    with col1:
        approval_login("TL")
    with col2:
        approval_login("BM")
    st.stop()

# ────────────────────────────────────────────────
# Authenticated - Set Title based on Role
# ────────────────────────────────────────────────
if st.session_state.role == "TL":
    st.title(f"Team Attendance – {st.session_state.username}")
    st.markdown("View your assigned employees' attendance. You can request edits (requires BM approval).")
elif st.session_state.role == "BM":
    st.title(f"Branch Attendance – {st.session_state.username}")
    st.markdown("View your assigned branch/region employees' attendance. You can edit directly or approve TL requests.")

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
# Get dynamic filter options (derived from loaded data)
# ────────────────────────────────────────────────
region_options = sorted(df["store_region"].dropna().unique().tolist())
status_options = sorted(df["status"].dropna().unique().tolist())

# ────────────────────────────────────────────────
# Sidebar filters
# ────────────────────────────────────────────────
with st.sidebar:
    st.header("Filters")
    region_filter = st.multiselect("Region", region_options)
    status_filter = st.multiselect("Status", status_options)

    col1, col2 = st.columns(2)
    with col1:
        date_from = st.date_input("From date", value=None)
    with col2:
        date_to = st.date_input("To date", value=None)

    edit_mode = False
    if st.session_state.role in ["TL", "BM"]:
        edit_mode = st.checkbox("Enable editing", value=False)

    st.success(f"{st.session_state.username} ({st.session_state.role})")
    if st.button("Logout"):
        logout()

    if st.button("Reload Data"):
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

# Assignment logic: TL sees only their employees, BM sees only their assigned branch/region employees
if st.session_state.role == "TL":
    filtered = filtered[filtered["tl_name"] == st.session_state.username]
elif st.session_state.role == "BM":
    filtered = filtered[filtered["bm_name"] == st.session_state.username]

if filtered.empty:
    st.warning("No data after applying filters or no employees assigned to you.")
    st.stop()

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
        "P": "background-color: lightgreen",
        "A": "background-color: lightcoral",
        "L": "background-color: orange",
        "H": "background-color: khaki",
        "WO": "background-color: khaki",
    }
    return colors.get(val, "background-color: lightgray")

# ────────────────────────────────────────────────
# Display Table (View or Edit Mode)
# ────────────────────────────────────────────────
if edit_mode:
    # ───── EDIT MODE ─────
    column_config = {
        "store_region": st.column_config.TextColumn(disabled=True, pinned=True),
        "userid": st.column_config.TextColumn(disabled=True, pinned=True),
        "name": st.column_config.TextColumn(disabled=True, pinned=True),
        "userstatus": st.column_config.TextColumn(disabled=True, pinned=True),
        "doj": st.column_config.TextColumn(disabled=True, pinned=True),
        "tl_name": st.column_config.TextColumn(disabled=True, pinned=True),
        "bm_name": st.column_config.TextColumn(disabled=True, pinned=True),
    }

    for col in date_columns:
        column_config[col] = st.column_config.SelectboxColumn(
            options=["", "P", "A", "L", "H", "WO"],
            required=False
        )

    edited_df = st.data_editor(
        display_pivot,
        column_config=column_config,
        use_container_width=True,
        height=700,
        hide_index=True,
        num_rows="fixed"
    )

    if st.session_state.role == "TL":
        remark = st.text_area("✍️ Remark (mandatory for submission)")

        if st.button("Submit Changes for BM Approval"):
            if not remark.strip():
                st.error("Remark is mandatory")
            else:
                changes_made = False
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
                            "level1_by": st.session_state.username,
                            "level1_at": datetime.utcnow().isoformat(),
                            "level1_status": "APPROVED",
                        }).execute()

                if changes_made:
                    st.success("Changes submitted for BM approval")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.info("No changes detected — nothing submitted.")

    elif st.session_state.role == "BM":
        if st.button("Save Changes Directly"):
            changes_made = False
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
                st.success("Changes saved directly to the database.")
                st.cache_data.clear()
                st.rerun()
            else:
                st.info("No changes detected — nothing saved.")

else:
    # ───── VIEW MODE ─────
    styled = display_pivot.style.map(color_status, subset=date_columns)

    st.dataframe(
        styled,
        use_container_width=True,
        height=700,
        hide_index=True,
        column_config={
            "store_region": st.column_config.TextColumn(pinned=True),
            "userid": st.column_config.TextColumn(pinned=True),
            "name": st.column_config.TextColumn(pinned=True),
            "userstatus": st.column_config.TextColumn(pinned=True),
            "doj": st.column_config.TextColumn(pinned=True),
            "tl_name": st.column_config.TextColumn(pinned=True),
            "bm_name": st.column_config.TextColumn(pinned=True),
        }
    )

# ────────────────────────────────────────────────
# BM Approval Bucket (only visible to BM)
# ────────────────────────────────────────────────
if st.session_state.role == "BM":
    st.subheader("🔵 Pending Approval Requests (from TLs)")

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
        st.info("No pending approval requests at this time.")
    else:
        for idx, r in reqs.iterrows():
            with st.expander(
                f"{r.userid} | {r.att_date} | {r.old_status} → {r.new_status} (Req ID: {r.id})"
            ):
                st.write("**Remark:**", r.remark)
                st.write(f"Requested by {r.level1_by} on {r.level1_at}")

                c1, c2 = st.columns(2)

                if c1.button("Approve", key=f"approve_{r.id}_{idx}"):
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

                if c2.button("Reject", key=f"reject_{r.id}_{idx}"):
                    supabase.table(REQ_TABLE).update({
                        "level2_status": "REJECTED",
                        "level2_by": st.session_state.username,
                        "level2_at": datetime.utcnow().isoformat(),
                    }).eq("id", r.id).execute()

                    st.warning(f"Request {r.id} rejected")
                    st.cache_data.clear()
                    st.rerun()

# ────────────────────────────────────────────────
# Download CSV
# ────────────────────────────────────────────────
st.download_button(
    "Download Current View as CSV",
    display_pivot.to_csv(index=False).encode("utf-8"),
    f"attendance_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
    mime="text/csv"
)

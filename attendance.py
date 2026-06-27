import streamlit as st
import pandas as pd
import sqlalchemy as sa
from datetime import datetime, date

# ────────────────────────────────────────────────
# Database settings (Supabase / Postgres)
# Set these in Streamlit Cloud -> App settings -> Secrets, e.g.:
#
# DB_USER = "postgres"
# DB_PASSWORD = "your-supabase-db-password"
# DB_HOST = "db.xxxxxxxx.supabase.co"
# DB_PORT = 6543
# DB_NAME = "postgres"
# ────────────────────────────────────────────────
DB_USER = st.secrets["DB_USER"]
DB_PASSWORD = st.secrets["DB_PASSWORD"]
DB_HOST = st.secrets["DB_HOST"]
DB_PORT = st.secrets["DB_PORT"]
DB_NAME = st.secrets["DB_NAME"]

ATT_TABLE = "attendance"
REQ_TABLE = "attendance_approval_requests"
USER_TABLE = "users"

connection_string = (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)
engine = sa.create_engine(connection_string)

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
        user = pd.read_sql(
            sa.text(
                f"""
                SELECT * FROM {USER_TABLE}
                WHERE username=:u AND password=:p AND role=:r
                """
            ),
            engine,
            params={"u": u, "p": p, "r": role_required},
        )
        if user.empty:
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
# Get dynamic filter options
# ────────────────────────────────────────────────
@st.cache_data(ttl=600)
def get_filter_options():
    regions = pd.read_sql(
        "SELECT DISTINCT store_region FROM attendance WHERE store_region IS NOT NULL",
        engine
    )["store_region"].tolist()

    statuses = pd.read_sql(
        "SELECT DISTINCT status FROM attendance WHERE status IS NOT NULL",
        engine
    )["status"].tolist()

    return sorted(regions), sorted(statuses)

region_options, status_options = get_filter_options()

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
# Load data
# ────────────────────────────────────────────────
@st.cache_data(ttl=600)
def load_data():
    df = pd.read_sql(
        """
        SELECT store_region, userid, name, userstatus, doj, tl_name, bm_name, date, status
        FROM attendance
        ORDER BY userid, date
        """,
        engine
    )
    df["date"] = pd.to_datetime(df["date"])
    df["doj"] = pd.to_datetime(df["doj"])
    return df

df = load_data()

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
                with engine.begin() as conn:
                    for i in range(len(edited_df)):
                        for d in date_columns:
                            old = display_pivot.iloc[i][d]
                            new = edited_df.iloc[i][d]

                            old_val = None if pd.isna(old) or old == "" else old
                            new_val = None if pd.isna(new) or new == "" else new

                            if old_val == new_val:
                                continue

                            changes_made = True
                            conn.execute(
                                sa.text("""
                                    INSERT INTO attendance_approval_requests
                                    (userid, att_date, old_status, new_status,
                                     remark, level1_by, level1_at, level1_status)
                                    VALUES
                                    (:u, :d, :o, :n, :r, :by, NOW(), 'APPROVED')
                                """),
                                {
                                    "u": edited_df.iloc[i]["userid"],
                                    "d": datetime.strptime(d, "%d-%m-%Y").date(),
                                    "o": old_val,
                                    "n": new_val,
                                    "r": remark,
                                    "by": st.session_state.username
                                }
                            )
                if changes_made:
                    st.success("Changes submitted for BM approval")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.info("No changes detected — nothing submitted.")

    elif st.session_state.role == "BM":
        if st.button("Save Changes Directly"):
            changes_made = False
            with engine.begin() as conn:
                for i in range(len(edited_df)):
                    for d in date_columns:
                        old = display_pivot.iloc[i][d]
                        new = edited_df.iloc[i][d]

                        old_val = None if pd.isna(old) or old == "" else old
                        new_val = None if pd.isna(new) or new == "" else new

                        if old_val == new_val:
                            continue

                        changes_made = True
                        conn.execute(
                            sa.text("""
                                UPDATE attendance
                                SET status = :s
                                WHERE userid = :u AND date = :d
                            """),
                            {
                                "s": new_val,
                                "u": edited_df.iloc[i]["userid"],
                                "d": datetime.strptime(d, "%d-%m-%Y").date()
                            }
                        )
            if changes_made:
                st.success("Changes saved directly to the database.")
                st.cache_data.clear()
                st.rerun()
            else:
                st.info("No changes detected — nothing saved.")

else:
    # ───── VIEW MODE ─────
    styled = display_pivot.style.applymap(color_status, subset=date_columns)

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

    reqs = pd.read_sql(
        """
        SELECT * FROM attendance_approval_requests
        WHERE level1_status='APPROVED'
          AND level2_status='PENDING'
        ORDER BY level1_at DESC
        """,
        engine
    )

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
                    with engine.begin() as conn:
                        conn.execute(
                            sa.text("""
                                UPDATE attendance
                                SET status = :s
                                WHERE userid = :u AND date = :d
                            """),
                            {"s": r.new_status, "u": r.userid, "d": r.att_date}
                        )
                        conn.execute(
                            sa.text("""
                                UPDATE attendance_approval_requests
                                SET level2_status = 'APPROVED',
                                    level2_by = :by,
                                    level2_at = NOW()
                                WHERE id = :id
                            """),
                            {"by": st.session_state.username, "id": r.id}
                        )
                    st.success(f"Request {r.id} approved")
                    st.rerun()

                if c2.button("Reject", key=f"reject_{r.id}_{idx}"):
                    with engine.begin() as conn:
                        conn.execute(
                            sa.text("""
                                UPDATE attendance_approval_requests
                                SET level2_status = 'REJECTED',
                                    level2_by = :by,
                                    level2_at = NOW()
                                WHERE id = :id
                            """),
                            {"by": st.session_state.username, "id": r.id}
                        )
                    st.warning(f"Request {r.id} rejected")
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

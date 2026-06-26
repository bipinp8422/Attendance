"""
app.py — Streamlit Attendance Change Request System (Supabase-backed).

Run with:  streamlit run app.py
"""

import streamlit as st
from datetime import date

import db
import auth_utils

st.set_page_config(page_title="Attendance Change Requests", page_icon="🗓️", layout="centered")


def _show_request_card(req: dict):
    c1, c2 = st.columns(2)
    with c1:
        st.write("**Attendance date:**", req["attendance_date"])
        st.write("**Original value:**", req["original_value"])
    with c2:
        st.write("**Requested value:**", req["requested_value"])
        st.write("**TL status:**", req["tl_status"], " | **BM status:**", req["bm_status"])
    st.write("**Reason:**", req["reason_remark"])


def _show_proof_link(req: dict):
    if req.get("proof_file_path"):
        try:
            url = db.get_proof_file_url(req["proof_file_path"])
            st.markdown(f"[📎 View attached approval email]({url})")
        except Exception:
            st.caption("Proof file could not be loaded.")


def _apply_decision(role: str, req: dict, approved: bool, remark: str):
    request_id = req["request_id"]
    if role == "tl":
        db.set_tl_decision(request_id, approved, remark)
        db.log_action(request_id, f"tl_{'approved' if approved else 'rejected'}",
                       remark, actor_user_id=st.session_state.user["user_id"])
    elif role == "bm":
        db.set_bm_decision(request_id, approved, remark)
        db.log_action(request_id, f"bm_{'approved' if approved else 'rejected'}",
                       remark, actor_user_id=st.session_state.user["user_id"])


# ════════════════════════════════════════════════════
#  1. Login
# ════════════════════════════════════════════════════

if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    st.title("🗓️ Attendance Change Request System")
    st.subheader("Login")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    if st.button("Log in", type="primary"):
        user = auth_utils.login(email, password)
        if user:
            st.session_state.user = user
            st.rerun()
        else:
            st.error("Invalid email or password.")
    st.stop()

user = st.session_state.user

st.sidebar.write(f"👤 **{user['full_name']}**")
st.sidebar.write(f"Role: `{user['role']}`")
if st.sidebar.button("Log out"):
    st.session_state.user = None
    st.rerun()


# ════════════════════════════════════════════════════
#  2. Employee view — submit + track requests
# ════════════════════════════════════════════════════

def employee_view():
    st.title("My Attendance Change Requests")

    with st.expander("➕ New change request", expanded=True):
        with st.form("new_request"):
            att_date = st.date_input("Attendance date", value=date.today())
            original = st.text_input("Original value (e.g. Absent, Half-day)")
            requested = st.text_input("Requested value (e.g. Present)")
            reason = st.text_area("Reason for the change")
            proof_file = st.file_uploader(
                "Attach the approval email you already received from your BM (PDF or image)",
                type=["pdf", "png", "jpg", "jpeg"]
            )
            submitted = st.form_submit_button("Submit request", type="primary")

        if submitted:
            if not (original and requested and reason and proof_file):
                st.error("Please fill in all fields and attach the BM approval email.")
            else:
                try:
                    proof_path = db.upload_proof_file(user["user_id"], proof_file.getvalue(), proof_file.name)
                    req = db.create_change_request(
                        user["user_id"], att_date, original, requested, reason,
                        proof_path, proof_file.name
                    )
                    db.log_action(req["request_id"], "submitted", reason, actor_user_id=user["user_id"])
                    st.success("Request submitted! Your Team Leader will review it next.")
                except RuntimeError as e:
                    st.error(str(e))

    st.subheader("History")
    my_requests = db.get_my_requests(user["user_id"])
    if not my_requests:
        st.info("No requests yet.")
    for req in my_requests:
        with st.container(border=True):
            _show_request_card(req)
            _show_proof_link(req)
            st.caption(f"Final status: **{req['final_status']}**")


# ════════════════════════════════════════════════════
#  3. Team Leader view
# ════════════════════════════════════════════════════

def tl_view():
    st.title("Pending Approvals — Team Leader")
    pending = db.get_pending_for_tl(user["user_id"])
    if not pending:
        st.info("No pending requests.")
    for req in pending:
        employee = db.get_user(req["employee_id"])
        with st.container(border=True):
            st.write(f"**Employee:** {employee['full_name']}")
            _show_request_card(req)
            _show_proof_link(req)
            remark = st.text_input("Remark", key=f"tl_remark_{req['request_id']}")
            c1, c2 = st.columns(2)
            if c1.button("✅ Approve", key=f"tl_appr_{req['request_id']}"):
                _apply_decision("tl", req, True, remark)
                st.rerun()
            if c2.button("❌ Reject", key=f"tl_rej_{req['request_id']}"):
                _apply_decision("tl", req, False, remark)
                st.rerun()


# ════════════════════════════════════════════════════
#  4. Business Manager view
# ════════════════════════════════════════════════════

def bm_view():
    st.title("Final Approvals — Business Manager")
    pending = db.get_pending_for_bm(user["user_id"])
    if not pending:
        st.info("No pending requests.")
    for req in pending:
        employee = db.get_user(req["employee_id"])
        with st.container(border=True):
            st.write(f"**Employee:** {employee['full_name']}")
            _show_request_card(req)
            _show_proof_link(req)
            remark = st.text_input("Remark", key=f"bm_remark_{req['request_id']}")
            c1, c2 = st.columns(2)
            if c1.button("✅ Approve", key=f"bm_appr_{req['request_id']}"):
                _apply_decision("bm", req, True, remark)
                st.rerun()
            if c2.button("❌ Reject", key=f"bm_rej_{req['request_id']}"):
                _apply_decision("bm", req, False, remark)
                st.rerun()


# ════════════════════════════════════════════════════
#  Route by role
# ════════════════════════════════════════════════════

if user["role"] == "employee":
    employee_view()
elif user["role"] == "tl":
    tl_view()
elif user["role"] == "bm":
    bm_view()
elif user["role"] == "admin":
    st.title("Admin")
    st.write("Add an admin dashboard here (manage users, view all requests, etc.) as needed.")
else:
    st.error("Unknown role.")

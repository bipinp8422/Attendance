"""
app.py — Streamlit Attendance Change Request System (Supabase-backed).

Run with:  streamlit run app.py

Flow:
  1. Employee logs in, submits a change request and uploads the approval
     email they already received from their BM (as proof).
  2. Team Leader logs into the app, reviews the proof, Approves/Rejects.
  3. If TL approves, the request shows up for the Business Manager, who
     logs in, reviews, and gives the final Approve/Reject.
  4. final_status becomes 'applied' (BM approved) or 'rejected'.

No emails are sent — everything happens inside the app.
"""

import streamlit as st
from datetime import date

import db
import auth_utils

# ════════════════════════════════════════════════════
#  Custom CSS for attractive styling
# ════════════════════════════════════════════════════

CUSTOM_CSS = """
<style>
    /* Hide default Streamlit header/footer */
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Main app background */
    .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1e1e2f 0%, #2d2d44 100%);
        border-right: 1px solid rgba(255,255,255,0.1);
    }
    
    [data-testid="stSidebar"] .stMarkdown {
        color: #e0e0e0;
    }
    
    /* Card containers - using key-based targeting */
    .st-key-request-card {
        background: white !important;
        border-radius: 16px !important;
        padding: 20px !important;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15) !important;
        border: 2px solid #e0e0e0 !important;
        margin-bottom: 16px !important;
    }
    
    .st-key-request-card [data-testid="stVerticalBlock"] {
        background: white !important;
    }
    
    /* Metric cards */
    .st-key-metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        border-radius: 16px !important;
        padding: 20px !important;
        text-align: center !important;
        color: white !important;
        border: none !important;
    }
    
    .st-key-metric-card [data-testid="stVerticalBlock"] {
        background: transparent !important;
    }
    
    /* Login card */
    .st-key-login-card {
        background: white !important;
        border-radius: 20px !important;
        padding: 40px !important;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3) !important;
    }
    
    .st-key-login-card [data-testid="stVerticalBlock"] {
        background: white !important;
    }
    
    /* Form card */
    .st-key-form-card {
        background: white !important;
        border-radius: 16px !important;
        padding: 24px !important;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1) !important;
        border: 2px solid #667eea !important;
    }
    
    .st-key-form-card [data-testid="stVerticalBlock"] {
        background: white !important;
    }
    
    /* Decision card */
    .st-key-decision-card {
        background: linear-gradient(135deg, #fff9e6 0%, #fff3cd 100%) !important;
        border-radius: 12px !important;
        padding: 16px !important;
        border: 2px solid #ffc107 !important;
    }
    
    .st-key-decision-card [data-testid="stVerticalBlock"] {
        background: transparent !important;
    }
    
    /* Proof link card */
    .st-key-proof-card {
        background: linear-gradient(135deg, #e7f3ff 0%, #d1ecf1 100%) !important;
        border-left: 4px solid #2196F3 !important;
        border-radius: 8px !important;
        padding: 12px 16px !important;
    }
    
    .st-key-proof-card [data-testid="stVerticalBlock"] {
        background: transparent !important;
    }
    
    /* Employee header card */
    .st-key-employee-header {
        background: linear-gradient(135deg, #667eea08 0%, #764ba208 100%) !important;
        border-radius: 12px !important;
        padding: 16px !important;
        border: 2px solid #667eea30 !important;
    }
    
    .st-key-employee-header [data-testid="stVerticalBlock"] {
        background: transparent !important;
    }
    
    /* Status badges */
    .status-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
        text-transform: uppercase;
    }
    
    .status-pending { background: #fff3cd; color: #856404; }
    .status-approved { background: #d4edda; color: #155724; }
    .status-rejected { background: #f8d7da; color: #721c24; }
    .status-applied { background: #d1ecf1; color: #0c5460; }
    
    /* Buttons */
    .stButton > button {
        border-radius: 12px !important;
        font-weight: 600 !important;
        transition: all 0.3s ease !important;
        text-transform: uppercase !important;
        letter-spacing: 0.5px !important;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2) !important;
    }
    
    /* Primary button */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        border: none !important;
    }
    
    /* Form inputs */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea {
        border-radius: 12px !important;
        border: 2px solid #e0e0e0 !important;
    }
    
    /* File uploader */
    .stFileUploader > div > div {
        border-radius: 12px !important;
        border: 2px dashed #667eea !important;
        background: rgba(102, 126, 234, 0.05) !important;
    }
    
    /* Expander styling */
    .streamlit-expanderHeader {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: white !important;
        border-radius: 12px !important;
        font-weight: 600 !important;
    }
    
    .streamlit-expanderContent {
        background: white !important;
        border-radius: 0 0 12px 12px !important;
        border: 2px solid #667eea !important;
        border-top: none !important;
    }
    
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0 !important;
        background: rgba(255,255,255,0.3) !important;
        color: white !important;
        font-weight: 600 !important;
    }
    
    .stTabs [aria-selected="true"] {
        background: white !important;
        color: #667eea !important;
    }
    
    /* Custom scrollbar */
    ::-webkit-scrollbar {
        width: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: #f1f1f1;
    }
    
    ::-webkit-scrollbar-thumb {
        background: #667eea;
        border-radius: 4px;
    }
</style>
"""

st.set_page_config(
    page_title="Attendance Change Requests",
    page_icon="🗓️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.html(CUSTOM_CSS)


# ════════════════════════════════════════════════════
#  Helper Functions
# ════════════════════════════════════════════════════

def _get_status_badge(status: str) -> str:
    """Return HTML badge for status."""
    status_class = {
        "pending": "status-pending",
        "approved": "status-approved",
        "rejected": "status-rejected",
        "applied": "status-applied"
    }.get(status.lower(), "status-pending")
    
    return f'<span class="status-badge {status_class}">{status.upper()}</span>'


def _show_request_card(req: dict):
    """Display request details in an attractive card layout."""
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        st.markdown("**📅 Attendance Date**")
        st.markdown(f"<h4 style='margin:0;color:#667eea;'>{req['attendance_date']}</h4>", unsafe_allow_html=True)
        st.markdown("**📝 Original Value**")
        st.markdown(f"<p style='margin:0;font-size:16px;'>{req['original_value']}</p>", unsafe_allow_html=True)
    
    with col2:
        st.markdown("**✏️ Requested Value**")
        st.markdown(f"<h4 style='margin:0;color:#764ba2;'>{req['requested_value']}</h4>", unsafe_allow_html=True)
        st.markdown("**📊 Status**")
        tl_badge = _get_status_badge(req["tl_status"])
        bm_badge = _get_status_badge(req["bm_status"])
        st.markdown(f"TL: {tl_badge} &nbsp; BM: {bm_badge}", unsafe_allow_html=True)
    
    with col3:
        final_status = req.get("final_status", "pending")
        st.markdown("**🏁 Final**")
        st.markdown(_get_status_badge(final_status), unsafe_allow_html=True)
    
    st.divider()
    st.markdown("**💬 Reason:**")
    st.info(req["reason_remark"])


def _show_proof_link(req: dict):
    """Display proof file link with attractive styling."""
    if req.get("proof_file_path"):
        try:
            url = db.get_proof_file_url(req["proof_file_path"])
            with st.container(key="proof-card", border=True):
                st.markdown(
                    f"""
                    <a href="{url}" target="_blank" style="
                        color: #2196F3;
                        text-decoration: none;
                        font-weight: 600;
                        font-size: 16px;
                    ">
                        📎 View Attached Approval Email
                    </a>
                    """,
                    unsafe_allow_html=True
                )
        except Exception:
            st.caption("⚠️ Proof file could not be loaded.")


def _apply_decision(role: str, req: dict, approved: bool, remark: str):
    """Apply approval/rejection decision."""
    request_id = req["request_id"]
    if role == "tl":
        db.set_tl_decision(request_id, approved, remark)
        db.log_action(
            request_id,
            f"tl_{'approved' if approved else 'rejected'}",
            remark,
            actor_user_id=st.session_state.user["user_id"]
        )
    elif role == "bm":
        db.set_bm_decision(request_id, approved, remark)
        db.log_action(
            request_id,
            f"bm_{'approved' if approved else 'rejected'}",
            remark,
            actor_user_id=st.session_state.user["user_id"]
        )


def _show_metrics(cards_data: list):
    """Display metric cards in a row."""
    cols = st.columns(len(cards_data))
    for idx, (col, (label, value, icon)) in enumerate(zip(cols, cards_data)):
        with col:
            with st.container(key=f"metric-card-{idx}", border=True):
                st.markdown(
                    f"""
                    <div style="text-align: center; color: white;">
                        <div style="font-size: 32px; margin-bottom: 8px;">{icon}</div>
                        <div style="font-size: 36px; font-weight: 700;">{value}</div>
                        <div style="font-size: 14px; opacity: 0.9; text-transform: uppercase; letter-spacing: 1px;">{label}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )


# ════════════════════════════════════════════════════
#  1. Login Panel
# ════════════════════════════════════════════════════

if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    # Center the login form
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        
        with st.container(key="login-card", border=True):
            st.markdown(
                """
                <div style="text-align: center; margin-bottom: 30px;">
                    <div style="font-size: 64px; margin-bottom: 10px;">🗓️</div>
                    <h1 style="margin: 0; color: #1e1e2f; font-size: 28px;">Attendance System</h1>
                    <p style="color: #888; margin-top: 8px; font-size: 16px;">Change Request Portal</p>
                </div>
                """,
                unsafe_allow_html=True
            )
            
            with st.form("login_form", clear_on_submit=False):
                email = st.text_input("📧 Email", placeholder="Enter your email")
                password = st.text_input("🔒 Password", type="password", placeholder="Enter your password")
                submitted = st.form_submit_button("Sign In", type="primary", use_container_width=True)
                
                if submitted:
                    user = auth_utils.login(email, password)
                    if user:
                        st.session_state.user = user
                        st.rerun()
                    else:
                        st.error("❌ Invalid email or password.")
    st.stop()


# ════════════════════════════════════════════════════
#  Sidebar (Post-Login)
# ════════════════════════════════════════════════════

user = st.session_state.user

with st.sidebar:
    # User profile card
    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 16px;
            padding: 24px;
            text-align: center;
            color: white;
            margin-bottom: 20px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.2);
        ">
            <div style="font-size: 48px; margin-bottom: 8px;">👤</div>
            <h3 style="margin: 0; color: white;">{user['full_name']}</h3>
            <p style="margin: 8px 0 0 0; opacity: 0.9; font-size: 14px;">
                Role: <strong>{user['role'].upper()}</strong>
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    st.divider()
    
    # Quick stats based on role
    if user["role"] == "employee":
        my_reqs = db.get_my_requests(user["user_id"])
        total = len(my_reqs)
        pending = sum(1 for r in my_reqs if r.get("final_status") == "pending")
        approved = sum(1 for r in my_reqs if r.get("final_status") == "applied")
        
        st.markdown("**📊 My Stats**")
        c1, c2 = st.columns(2)
        c1.metric("Total", total)
        c2.metric("Pending", pending)
        st.metric("Approved", approved)
        
    elif user["role"] == "tl":
        pending_tl = len(db.get_pending_for_tl(user["user_id"]))
        st.metric("⏳ Pending Reviews", pending_tl)
        
    elif user["role"] == "bm":
        pending_bm = len(db.get_pending_for_bm(user["user_id"]))
        st.metric("⏳ Final Reviews", pending_bm)
    
    st.divider()
    
    if st.button("🚪 Log Out", use_container_width=True):
        st.session_state.user = None
        st.rerun()


# ════════════════════════════════════════════════════
#  2. Employee View
# ════════════════════════════════════════════════════

def employee_view():
    st.title("👨‍💼 My Attendance Dashboard")
    
    # Metrics row
    my_requests = db.get_my_requests(user["user_id"])
    total = len(my_requests)
    pending = sum(1 for r in my_requests if r.get("final_status") == "pending")
    approved = sum(1 for r in my_requests if r.get("final_status") == "applied")
    rejected = sum(1 for r in my_requests if r.get("final_status") == "rejected")
    
    _show_metrics([
        ("Total Requests", total, "📋"),
        ("Pending", pending, "⏳"),
        ("Approved", approved, "✅"),
        ("Rejected", rejected, "❌")
    ])
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # New request form
    with st.expander("➕ Submit New Change Request", expanded=True):
        with st.container(key="form-card", border=True):
            with st.form("new_request", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    att_date = st.date_input("📅 Attendance Date", value=date.today())
                    original = st.text_input("📝 Original Value", placeholder="e.g., Absent, Half-day")
                with col2:
                    requested = st.text_input("✏️ Requested Value", placeholder="e.g., Present")
                    reason = st.text_area("💬 Reason for Change", placeholder="Explain why you need this change...")
                
                proof_file = st.file_uploader(
                    "📎 Attach BM Approval Email (PDF or Image)",
                    type=["pdf", "png", "jpg", "jpeg"],
                    help="Upload the approval email you already received from your Business Manager"
                )
                
                submitted = st.form_submit_button("🚀 Submit Request", type="primary", use_container_width=True)
                
                if submitted:
                    if not (original and requested and reason and proof_file):
                        st.error("⚠️ Please fill in all fields and attach the BM approval email.")
                    else:
                        with st.spinner("Processing your request..."):
                            proof_path = db.upload_proof_file(
                                user["user_id"],
                                proof_file.getvalue(),
                                proof_file.name
                            )
                            req = db.create_change_request(
                                user["user_id"],
                                att_date,
                                original,
                                requested,
                                reason,
                                proof_path,
                                proof_file.name
                            )
                            db.log_action(
                                req["request_id"],
                                "submitted",
                                reason,
                                actor_user_id=user["user_id"]
                            )
                        st.success("✅ Request submitted successfully! Your Team Leader will review it next.")
                        st.balloons()
    
    # History section
    st.subheader("📜 Request History")
    
    if not my_requests:
        st.info("📭 No requests yet. Submit your first request above!")
    else:
        # Filter tabs
        tab1, tab2, tab3, tab4 = st.tabs(["🔄 All", "⏳ Pending", "✅ Approved", "❌ Rejected"])
        
        with tab1:
            for req in my_requests:
                _render_request_card(req)
        
        with tab2:
            pending_reqs = [r for r in my_requests if r.get("final_status") == "pending"]
            if not pending_reqs:
                st.info("No pending requests.")
            for req in pending_reqs:
                _render_request_card(req)
        
        with tab3:
            approved_reqs = [r for r in my_requests if r.get("final_status") == "applied"]
            if not approved_reqs:
                st.info("No approved requests yet.")
            for req in approved_reqs:
                _render_request_card(req)
        
        with tab4:
            rejected_reqs = [r for r in my_requests if r.get("final_status") == "rejected"]
            if not rejected_reqs:
                st.info("No rejected requests.")
            for req in rejected_reqs:
                _render_request_card(req)


def _render_request_card(req: dict):
    """Render a single request card for employee view."""
    with st.container(key="request-card", border=True):
        _show_request_card(req)
        _show_proof_link(req)


# ════════════════════════════════════════════════════
#  3. Team Leader View
# ════════════════════════════════════════════════════

def tl_view():
    st.title("👔 Team Leader Dashboard")
    
    pending = db.get_pending_for_tl(user["user_id"])
    total_pending = len(pending)
    
    # Metrics
    _show_metrics([
        ("Pending Reviews", total_pending, "⏳"),
        ("My Team Size", "—", "👥"),
        ("Avg Response Time", "—", "⏱️")
    ])
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    st.subheader("🔍 Pending Approvals")
    
    if not pending:
        st.success("🎉 All caught up! No pending requests to review.")
    else:
        for req in pending:
            employee = db.get_user(req["employee_id"])
            
            with st.container(key="request-card", border=True):
                # Employee info header
                with st.container(key="employee-header", border=True):
                    col1, col2 = st.columns([1, 6])
                    with col1:
                        st.markdown("<div style='font-size: 40px; text-align: center;'>👤</div>", unsafe_allow_html=True)
                    with col2:
                        st.markdown(f"<h4 style='margin: 0; color: #1e1e2f;'>{employee['full_name']}</h4>", unsafe_allow_html=True)
                        st.markdown(f"<p style='margin: 0; color: #888; font-size: 13px;'>Employee ID: {req['employee_id']}</p>", unsafe_allow_html=True)
                
                _show_request_card(req)
                _show_proof_link(req)
                
                # Decision section
                with st.container(key="decision-card", border=True):
                    st.markdown("**📝 Your Decision**")
                    remark = st.text_area(
                        "Add a remark (optional)",
                        key=f"tl_remark_{req['request_id']}",
                        placeholder="Enter your remarks here..."
                    )
                    
                    col1, col2, col3 = st.columns([1, 1, 2])
                    with col1:
                        if st.button(
                            "✅ Approve",
                            key=f"tl_appr_{req['request_id']}",
                            type="primary",
                            use_container_width=True
                        ):
                            _apply_decision("tl", req, True, remark)
                            st.success("✅ Approved!")
                            st.rerun()
                    
                    with col2:
                        if st.button(
                            "❌ Reject",
                            key=f"tl_rej_{req['request_id']}",
                            type="secondary",
                            use_container_width=True
                        ):
                            _apply_decision("tl", req, False, remark)
                            st.error("❌ Rejected!")
                            st.rerun()


# ════════════════════════════════════════════════════
#  4. Business Manager View
# ════════════════════════════════════════════════════

def bm_view():
    st.title("💼 Business Manager Dashboard")
    
    pending = db.get_pending_for_bm(user["user_id"])
    total_pending = len(pending)
    
    # Metrics
    _show_metrics([
        ("Final Reviews", total_pending, "⏳"),
        ("Approved Today", "—", "✅"),
        ("Rejection Rate", "—", "📊")
    ])
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    st.subheader("🔍 Final Approvals")
    
    if not pending:
        st.success("🎉 All caught up! No pending final approvals.")
    else:
        for req in pending:
            employee = db.get_user(req["employee_id"])
            tl_remark = req.get("tl_remark", "No remarks")
            
            with st.container(key="request-card", border=True):
                # Employee info header
                with st.container(key="employee-header", border=True):
                    col1, col2 = st.columns([1, 6])
                    with col1:
                        st.markdown("<div style='font-size: 40px; text-align: center;'>👤</div>", unsafe_allow_html=True)
                    with col2:
                        st.markdown(f"<h4 style='margin: 0; color: #1e1e2f;'>{employee['full_name']}</h4>", unsafe_allow_html=True)
                        st.markdown(f"<p style='margin: 0; color: #888; font-size: 13px;'>TL Status: <strong>{req['tl_status'].upper()}</strong></p>", unsafe_allow_html=True)
                
                # TL decision info
                if tl_remark and tl_remark != "No remarks":
                    st.markdown(
                        f"""
                        <div style="
                            background: #e7f3ff;
                            border-left: 4px solid #2196F3;
                            padding: 12px 16px;
                            border-radius: 8px;
                            margin-bottom: 16px;
                        ">
                            <strong>📝 TL Remark:</strong> {tl_remark}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                
                _show_request_card(req)
                _show_proof_link(req)
                
                # Decision section
                with st.container(key="decision-card", border=True):
                    st.markdown("**📝 Final Decision**")
                    remark = st.text_area(
                        "Add a remark (optional)",
                        key=f"bm_remark_{req['request_id']}",
                        placeholder="Enter your final remarks here..."
                    )
                    
                    col1, col2, col3 = st.columns([1, 1, 2])
                    with col1:
                        if st.button(
                            "✅ Final Approve",
                            key=f"bm_appr_{req['request_id']}",
                            type="primary",
                            use_container_width=True
                        ):
                            _apply_decision("bm", req, True, remark)
                            st.success("✅ Final approval granted!")
                            st.balloons()
                            st.rerun()
                    
                    with col2:
                        if st.button(
                            "❌ Final Reject",
                            key=f"bm_rej_{req['request_id']}",
                            type="secondary",
                            use_container_width=True
                        ):
                            _apply_decision("bm", req, False, remark)
                            st.error("❌ Request rejected!")
                            st.rerun()


# ════════════════════════════════════════════════════
#  5. Admin View
# ════════════════════════════════════════════════════

def admin_view():
    st.title("🔧 Admin Dashboard")
    
    _show_metrics([
        ("Total Users", "—", "👥"),
        ("Total Requests", "—", "📋"),
        ("Pending Actions", "—", "⏳")
    ])
    
    with st.container(key="request-card", border=True):
        st.info("🛠️ Admin dashboard is under development. Features coming soon:")
        st.markdown("""
        - 👥 User Management
        - 📊 Analytics & Reports  
        - ⚙️ System Configuration
        - 📈 Performance Metrics
        """)


# ════════════════════════════════════════════════════
#  Route by Role
# ════════════════════════════════════════════════════

if user["role"] == "employee":
    employee_view()
elif user["role"] == "tl":
    tl_view()
elif user["role"] == "bm":
    bm_view()
elif user["role"] == "admin":
    admin_view()
else:
    st.error("⚠️ Unknown role. Please contact your administrator.")

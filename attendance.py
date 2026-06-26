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
    /* Main background */
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
    
    /* Card containers */
    .stContainer {
        background: rgba(255, 255, 255, 0.95);
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.2);
        margin-bottom: 16px;
    }
    
    /* Buttons */
    .stButton > button {
        border-radius: 12px;
        font-weight: 600;
        transition: all 0.3s ease;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    }
    
    /* Primary button */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border: none;
    }
    
    /* Form inputs */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea {
        border-radius: 12px;
        border: 2px solid #e0e0e0;
        transition: all 0.3s ease;
    }
    
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: #667eea;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
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
    
    /* Login card */
    .login-card {
        background: white;
        border-radius: 20px;
        padding: 40px;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        max-width: 400px;
        margin: 0 auto;
    }
    
    /* Metric cards */
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 16px;
        padding: 20px;
        text-align: center;
    }
    
    .metric-value {
        font-size: 32px;
        font-weight: 700;
    }
    
    .metric-label {
        font-size: 14px;
        opacity: 0.9;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    /* Section headers */
    h1, h2, h3 {
        color: #1e1e2f;
    }
    
    /* Expander styling */
    .streamlit-expanderHeader {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white !important;
        border-radius: 12px;
        font-weight: 600;
    }
    
    .streamlit-expanderContent {
        background: rgba(255, 255, 255, 0.95);
        border-radius: 0 0 12px 12px;
    }
    
    /* File uploader */
    .stFileUploader > div > div {
        border-radius: 12px;
        border: 2px dashed #667eea;
        background: rgba(102, 126, 234, 0.05);
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

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


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
            st.markdown(
                f"""
                <div style="
                    background: linear-gradient(135deg, #667eea15 0%, #764ba215 100%);
                    border-left: 4px solid #667eea;
                    padding: 12px 16px;
                    border-radius: 8px;
                    margin-top: 12px;
                ">
                    <a href="{url}" target="_blank" style="
                        color: #667eea;
                        text-decoration: none;
                        font-weight: 600;
                        display: flex;
                        align-items: center;
                        gap: 8px;
                    ">
                        📎 View Attached Approval Email
                    </a>
                </div>
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
    for col, (label, value, icon) in zip(cols, cards_data):
        with col:
            st.markdown(
                f"""
                <div class="metric-card">
                    <div style="font-size: 28px; margin-bottom: 8px;">{icon}</div>
                    <div class="metric-value">{value}</div>
                    <div class="metric-label">{label}</div>
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
        st.markdown(
            """
            <div class="login-card">
                <div style="text-align: center; margin-bottom: 30px;">
                    <div style="font-size: 48px; margin-bottom: 10px;">🗓️</div>
                    <h1 style="margin: 0; color: #1e1e2f; font-size: 28px;">Attendance System</h1>
                    <p style="color: #888; margin-top: 8px;">Change Request Portal</p>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # Use a form for the actual inputs (Streamlit forms)
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
        
        st.markdown("</div>", unsafe_allow_html=True)
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
        st.markdown(
            """
            <div style="
                background: linear-gradient(135deg, #667eea08 0%, #764ba208 100%);
                border-radius: 12px;
                padding: 20px;
            ">
            """,
            unsafe_allow_html=True
        )
        
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
        
        st.markdown("</div>", unsafe_allow_html=True)
    
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
    with st.container(border=True):
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
        ("My Team Size", "—", "👥"),  # You can add actual team size query
        ("Avg Response Time", "—", "⏱️")  # You can add actual metric
    ])
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    st.subheader("🔍 Pending Approvals")
    
    if not pending:
        st.success("🎉 All caught up! No pending requests to review.")
    else:
        for req in pending:
            employee = db.get_user(req["employee_id"])
            
            with st.container(border=True):
                # Header with employee info
                st.markdown(
                    f"""
                    <div style="
                        display: flex;
                        align-items: center;
                        gap: 12px;
                        margin-bottom: 16px;
                        padding: 12px;
                        background: linear-gradient(135deg, #667eea08 0%, #764ba208 100%);
                        border-radius: 12px;
                    ">
                        <div style="font-size: 32px;">👤</div>
                        <div>
                            <h4 style="margin: 0; color: #1e1e2f;">{employee['full_name']}</h4>
                            <p style="margin: 0; color: #888; font-size: 13px;">Employee ID: {req['employee_id']}</p>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                
                _show_request_card(req)
                _show_proof_link(req)
                
                # Decision section
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
        ("Approved Today", "—", "✅"),  # Add actual query
        ("Rejection Rate", "—", "📊")   # Add actual query
    ])
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    st.subheader("🔍 Final Approvals")
    
    if not pending:
        st.success("🎉 All caught up! No pending final approvals.")
    else:
        for req in pending:
            employee = db.get_user(req["employee_id"])
            tl_remark = req.get("tl_remark", "No remarks")
            
            with st.container(border=True):
                # Employee info header
                st.markdown(
                    f"""
                    <div style="
                        display: flex;
                        align-items: center;
                        gap: 12px;
                        margin-bottom: 16px;
                        padding: 12px;
                        background: linear-gradient(135deg, #667eea08 0%, #764ba208 100%);
                        border-radius: 12px;
                    ">
                        <div style="font-size: 32px;">👤</div>
                        <div>
                            <h4 style="margin: 0; color: #1e1e2f;">{employee['full_name']}</h4>
                            <p style="margin: 0; color: #888; font-size: 13px;">
                                TL Status: <strong>{req['tl_status'].upper()}</strong>
                            </p>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                
                # TL decision info
                if tl_remark:
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

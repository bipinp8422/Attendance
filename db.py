"""
db.py — Supabase data-access layer for the Attendance Change Request System.

Uses the Supabase SERVICE_ROLE key (server-side only, never exposed to
the browser) so it bypasses Row Level Security. All access control is
handled in the Streamlit app itself (login + role checks).
"""

import os
import uuid
from datetime import datetime, date
from typing import Optional

from supabase import create_client, Client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
PROOF_BUCKET = os.environ.get("SUPABASE_PROOF_BUCKET", "approval-proofs")

_client: Optional[Client] = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _client


# ────────────────────────────────────────────────
#  Users
# ────────────────────────────────────────────────

def get_user(user_id: str) -> Optional[dict]:
    sb = get_client()
    res = sb.table("users").select("*").eq("user_id", user_id).execute()
    return res.data[0] if res.data else None


def get_user_by_email(email: str) -> Optional[dict]:
    sb = get_client()
    res = sb.table("users").select("*").eq("email", email).execute()
    return res.data[0] if res.data else None


def create_user(user_id, full_name, role, email, password_hash,
                 team_leader_id=None, business_manager_id=None) -> dict:
    sb = get_client()
    payload = {
        "user_id": user_id,
        "full_name": full_name,
        "role": role,
        "email": email,
        "password_hash": password_hash,
        "team_leader_id": team_leader_id,
        "business_manager_id": business_manager_id,
    }
    res = sb.table("users").insert(payload).execute()
    return res.data[0]


# ────────────────────────────────────────────────
#  File upload (proof of BM approval email)
# ────────────────────────────────────────────────

def upload_proof_file(employee_id: str, file_bytes: bytes, original_filename: str) -> str:
    """Uploads to Supabase Storage, returns the storage object path."""
    sb = get_client()
    ext = original_filename.rsplit(".", 1)[-1] if "." in original_filename else "bin"
    path = f"{employee_id}/{uuid.uuid4().hex}.{ext}"
    sb.storage.from_(PROOF_BUCKET).upload(
        path, file_bytes,
        file_options={"content-type": "application/octet-stream"}
    )
    return path


def get_proof_file_url(path: str, expires_in: int = 3600) -> str:
    """Returns a temporary signed URL so TL/BM can view the proof file."""
    sb = get_client()
    res = sb.storage.from_(PROOF_BUCKET).create_signed_url(path, expires_in)
    return res["signedURL"] if "signedURL" in res else res.get("signed_url", "")


# ────────────────────────────────────────────────
#  Change requests
# ────────────────────────────────────────────────

def create_change_request(employee_id: str, attendance_date: date, original: str,
                            requested: str, reason: str, proof_file_path: str,
                            proof_file_name: str) -> dict:
    sb = get_client()
    payload = {
        "employee_id": employee_id,
        "attendance_date": attendance_date.isoformat() if isinstance(attendance_date, date) else attendance_date,
        "original_value": original,
        "requested_value": requested,
        "reason_remark": reason,
        "proof_file_path": proof_file_path,
        "proof_file_name": proof_file_name,
    }
    res = sb.table("change_requests").insert(payload).execute()
    return res.data[0]


def get_request(request_id: int) -> Optional[dict]:
    sb = get_client()
    res = sb.table("change_requests").select("*").eq("request_id", request_id).execute()
    return res.data[0] if res.data else None


def get_request_by_token(token: str, role: str) -> Optional[dict]:
    """role is 'tl' or 'bm' — looks up by tl_token or bm_token."""
    col = "tl_token" if role == "tl" else "bm_token"
    sb = get_client()
    res = sb.table("change_requests").select("*").eq(col, token).execute()
    return res.data[0] if res.data else None


def get_my_requests(employee_id: str) -> list[dict]:
    sb = get_client()
    res = (sb.table("change_requests").select("*")
           .eq("employee_id", employee_id)
           .order("created_at", desc=True).execute())
    return res.data


def get_pending_for_tl(tl_id: str) -> list[dict]:
    """All pending requests from employees who report to this TL."""
    sb = get_client()
    emp_res = sb.table("users").select("user_id").eq("team_leader_id", tl_id).execute()
    employee_ids = [u["user_id"] for u in emp_res.data]
    if not employee_ids:
        return []
    res = (sb.table("change_requests").select("*")
           .in_("employee_id", employee_ids)
           .eq("tl_status", "pending")
           .order("created_at").execute())
    return res.data


def get_pending_for_bm(bm_id: str) -> list[dict]:
    """All TL-approved, BM-pending requests from employees under this BM."""
    sb = get_client()
    emp_res = sb.table("users").select("user_id").eq("business_manager_id", bm_id).execute()
    employee_ids = [u["user_id"] for u in emp_res.data]
    if not employee_ids:
        return []
    res = (sb.table("change_requests").select("*")
           .in_("employee_id", employee_ids)
           .eq("tl_status", "approved")
           .eq("bm_status", "pending")
           .order("created_at").execute())
    return res.data


def set_tl_decision(request_id: int, approved: bool, remark: str = "") -> dict:
    sb = get_client()
    payload = {
        "tl_status": "approved" if approved else "rejected",
        "tl_remark": remark,
        "tl_timestamp": datetime.utcnow().isoformat(),
    }
    if not approved:
        payload["final_status"] = "rejected"
    res = sb.table("change_requests").update(payload).eq("request_id", request_id).execute()
    return res.data[0]


def set_bm_decision(request_id: int, approved: bool, remark: str = "") -> dict:
    sb = get_client()
    payload = {
        "bm_status": "approved" if approved else "rejected",
        "bm_remark": remark,
        "bm_timestamp": datetime.utcnow().isoformat(),
        "final_status": "applied" if approved else "rejected",
    }
    res = sb.table("change_requests").update(payload).eq("request_id", request_id).execute()
    return res.data[0]


# ────────────────────────────────────────────────
#  Audit log
# ────────────────────────────────────────────────

def log_action(request_id: int, action: str, remark: str = "",
                actor_user_id: str = None, actor_label: str = None):
    sb = get_client()
    payload = {
        "request_id": request_id,
        "action": action,
        "remark": remark,
        "actor_user_id": actor_user_id,
        "actor_label": actor_label,
    }
    sb.table("audit_log").insert(payload).execute()


def get_audit_trail(request_id: int) -> list[dict]:
    sb = get_client()
    res = (sb.table("audit_log").select("*")
           .eq("request_id", request_id)
           .order("timestamp").execute())
    return res.data

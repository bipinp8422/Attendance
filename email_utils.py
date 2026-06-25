"""
email_utils.py — sends approval-link emails to TL / BM using SMTP.

Works with any SMTP provider (Gmail, Outlook, SendGrid SMTP, etc).
Set these environment variables:
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM
    APP_BASE_URL   e.g. https://your-streamlit-app.streamlit.app
"""

import os
import smtplib
from email.mime.text import MIMEText

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER)
APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:8501")


def _send(to_email: str, subject: str, body_html: str):
    msg = MIMEText(body_html, "html")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_email

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_FROM, [to_email], msg.as_string())


def _approval_link(token: str, role: str, action: str) -> str:
    return f"{APP_BASE_URL}/?token={token}&role={role}&action={action}"


def send_tl_approval_request(tl_email: str, tl_name: str, request: dict, employee_name: str):
    token = request["tl_token"]
    approve_url = _approval_link(token, "tl", "approve")
    reject_url = _approval_link(token, "tl", "reject")

    body = f"""
    <p>Hi {tl_name},</p>
    <p><b>{employee_name}</b> has requested an attendance change for
    <b>{request['attendance_date']}</b>:</p>
    <ul>
      <li>Original value: <b>{request['original_value']}</b></li>
      <li>Requested value: <b>{request['requested_value']}</b></li>
      <li>Reason: {request['reason_remark']}</li>
    </ul>
    <p>The employee has attached their BM approval email as proof.
    Review it in the app before deciding.</p>
    <p>
      <a href="{approve_url}" style="padding:8px 16px;background:#2e7d32;color:white;text-decoration:none;border-radius:4px;">Approve</a>
      &nbsp;
      <a href="{reject_url}" style="padding:8px 16px;background:#c62828;color:white;text-decoration:none;border-radius:4px;">Reject</a>
    </p>
    <p>Or open the app to review full details: {APP_BASE_URL}</p>
    """
    _send(tl_email, f"Attendance Change Approval Needed — {employee_name}", body)


def send_bm_approval_request(bm_email: str, bm_name: str, request: dict, employee_name: str):
    token = request["bm_token"]
    approve_url = _approval_link(token, "bm", "approve")
    reject_url = _approval_link(token, "bm", "reject")

    body = f"""
    <p>Hi {bm_name},</p>
    <p><b>{employee_name}</b>'s attendance change request for
    <b>{request['attendance_date']}</b> has been approved by the Team Leader
    and now needs your final approval:</p>
    <ul>
      <li>Original value: <b>{request['original_value']}</b></li>
      <li>Requested value: <b>{request['requested_value']}</b></li>
      <li>Reason: {request['reason_remark']}</li>
    </ul>
    <p>
      <a href="{approve_url}" style="padding:8px 16px;background:#2e7d32;color:white;text-decoration:none;border-radius:4px;">Approve</a>
      &nbsp;
      <a href="{reject_url}" style="padding:8px 16px;background:#c62828;color:white;text-decoration:none;border-radius:4px;">Reject</a>
    </p>
    <p>Or open the app to review full details: {APP_BASE_URL}</p>
    """
    _send(bm_email, f"Final Approval Needed — {employee_name}", body)


def send_status_update(employee_email: str, employee_name: str, request: dict, final_status: str):
    body = f"""
    <p>Hi {employee_name},</p>
    <p>Your attendance change request for <b>{request['attendance_date']}</b>
    has been <b>{final_status.upper()}</b>.</p>
    <p>Requested change: {request['original_value']} → {request['requested_value']}</p>
    """
    _send(employee_email, f"Attendance Change Request — {final_status.upper()}", body)

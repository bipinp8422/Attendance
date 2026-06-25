"""
auth_utils.py — password hashing and login check.
"""

import bcrypt
import db


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def login(email: str, password: str):
    """Returns the user dict on success, None on failure."""
    user = db.get_user_by_email(email)
    if user and verify_password(password, user["password_hash"]):
        return user
    return None

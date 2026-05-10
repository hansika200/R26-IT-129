"""
services/auth_service.py
========================
Authentication service — registration, login, and JWT management.
Now using MongoDB via UserRepository.

Research Component: SLSL Recognition System — Objective 4
"""

import logging
from typing import Optional, Tuple
from datetime import datetime

import bcrypt
from flask_jwt_extended import create_access_token

from repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

def hash_password(plain: str) -> str:
    """Hash a plain-text password using bcrypt."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    """Return True if plain matches the bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False

# ── Registration ──────────────────────────────────────────────────────────────

def register_user(
    username: str,
    email: str,
    password: str,
    full_name: str = "",
    role: str = "teacher",
) -> Tuple[bool, str, Optional[dict]]:
    try:
        existing = UserRepository.get_by_username_or_email(username, email)
        if existing:
            return False, "Username or email already exists.", None

        pw_hash = hash_password(password)
        now = datetime.utcnow().isoformat()
        payload = {
            "username": username,
            "email": email,
            "password_hash": pw_hash,
            "full_name": full_name,
            "role": role,
            "is_active": 1,
            "created_at": now,
            "updated_at": now,
        }
        
        user = UserRepository.create_user(payload)
        user.pop("password_hash", None)
        return True, "User registered successfully.", user

    except Exception as exc:
        logger.exception("Registration failed for '%s': %s", username, exc)
        return False, f"Registration failed: {exc}", None

# ── Login ─────────────────────────────────────────────────────────────────────

def login_user(username: str, password: str) -> Tuple[bool, str, Optional[dict]]:
    try:
        user = UserRepository.get_by_username(username)
        if not user:
            return False, "Invalid username or password.", None

        if not verify_password(password, user["password_hash"]):
            return False, "Invalid username or password.", None

        token = create_access_token(
            identity=str(user["_id"]),
            additional_claims={"role": user["role"], "username": user["username"]},
        )
        user.pop("password_hash", None)
        return True, token, user

    except Exception as exc:
        logger.exception("Login failed for '%s': %s", username, exc)
        return False, f"Login failed: {exc}", None

# ── User lookup ───────────────────────────────────────────────────────────────

def get_user_by_id(user_id: str) -> Optional[dict]:
    try:
        user = UserRepository.get_by_id(user_id)
        if user:
            user.pop("password_hash", None)
        return user
    except Exception as exc:
        logger.exception("get_user_by_id(%s) failed: %s", user_id, exc)
        return None

def list_users(role: Optional[str] = None) -> list:
    try:
        users = UserRepository.list_users(role)
        for u in users:
            u.pop("password_hash", None)
        return users
    except Exception as exc:
        logger.exception("list_users failed: %s", exc)
        return []

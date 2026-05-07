"""
services/auth_service.py
========================
Authentication service — registration, login, and JWT management.

Uses bcrypt for password hashing and flask-jwt-extended for token issuance.

Research Component: SLSL Recognition System — Objective 4
Author: Hansika
"""

import logging
from typing import Optional, Tuple

import bcrypt
from flask_jwt_extended import create_access_token

from database.db import db_context, rows_to_list, row_to_dict
from database.models import UserModel
from utils.helpers import utcnow_iso

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
    """
    Register a new teacher/admin account.

    Returns:
        (success, message, user_dict)
    """
    try:
        with db_context() as conn:
            # Check uniqueness
            existing = conn.execute(
                "SELECT id FROM users WHERE username = ? OR email = ?",
                (username, email)
            ).fetchone()
            if existing:
                return False, "Username or email already exists.", None

            pw_hash = hash_password(password)
            payload = UserModel.create_payload(username, email, pw_hash, full_name, role)

            cursor = conn.execute(
                """INSERT INTO users (username, email, password_hash, full_name, role, is_active, created_at, updated_at)
                   VALUES (:username, :email, :password_hash, :full_name, :role, :is_active, :created_at, :updated_at)""",
                payload,
            )
            user_id = cursor.lastrowid
            user = row_to_dict(
                conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            )
            return True, "User registered successfully.", UserModel.safe_dict(user)

    except Exception as exc:
        logger.exception("Registration failed for '%s': %s", username, exc)
        return False, f"Registration failed: {exc}", None


# ── Login ─────────────────────────────────────────────────────────────────────

def login_user(username: str, password: str) -> Tuple[bool, str, Optional[dict]]:
    """
    Validate credentials and issue a JWT access token.

    Returns:
        (success, message_or_token, user_dict)
    """
    try:
        with db_context() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ? AND is_active = 1",
                (username,)
            ).fetchone()

        if not row:
            return False, "Invalid username or password.", None

        user = dict(row)
        if not verify_password(password, user["password_hash"]):
            return False, "Invalid username or password.", None

        # Issue JWT — identity includes role for RBAC
        token = create_access_token(
            identity=str(user["id"]),
            additional_claims={"role": user["role"], "username": user["username"]},
        )
        return True, token, UserModel.safe_dict(user)

    except Exception as exc:
        logger.exception("Login failed for '%s': %s", username, exc)
        return False, f"Login failed: {exc}", None


# ── User lookup ───────────────────────────────────────────────────────────────

def get_user_by_id(user_id: int) -> Optional[dict]:
    """Return a user dict (without password_hash) or None."""
    try:
        with db_context() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        if row:
            return UserModel.safe_dict(row_to_dict(row))
        return None
    except Exception as exc:
        logger.exception("get_user_by_id(%s) failed: %s", user_id, exc)
        return None


def list_users(role: Optional[str] = None) -> list:
    """Return all users, optionally filtered by role."""
    try:
        with db_context() as conn:
            if role:
                rows = conn.execute(
                    "SELECT * FROM users WHERE role = ? ORDER BY created_at DESC", (role,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM users ORDER BY created_at DESC"
                ).fetchall()
        return [UserModel.safe_dict(dict(r)) for r in rows]
    except Exception as exc:
        logger.exception("list_users failed: %s", exc)
        return []

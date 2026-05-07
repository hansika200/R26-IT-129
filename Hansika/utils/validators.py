"""
utils/validators.py
===================
Request validation helpers.
Used by route handlers to validate incoming JSON bodies and file uploads.

Research Component: SLSL Recognition System — Objective 4
Author: Hansika
"""

import re
from pathlib import Path
from typing import Optional

from config.settings import get_config

cfg = get_config()


# ── Generic helpers ──────────────────────────────────────────────────────────

def is_non_empty_string(value) -> bool:
    """Return True if value is a non-empty string."""
    return isinstance(value, str) and bool(value.strip())


def is_valid_email(email: str) -> bool:
    """Basic e-mail format validation."""
    pattern = r"^[\w\.\+\-]+@[\w\-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def is_valid_role(role: str) -> bool:
    return role in {"teacher", "admin"}


def clamp_int(value, min_val: int, max_val: int) -> int:
    """Clamp an integer between min/max bounds."""
    try:
        return max(min_val, min(int(value), max_val))
    except (TypeError, ValueError):
        return min_val


# ── Auth validators ──────────────────────────────────────────────────────────

def validate_register_payload(data: dict) -> Optional[str]:
    """
    Validate /auth/register request body.
    Returns error message string on failure, None on success.
    """
    if not data:
        return "Request body is required."

    required = ["username", "email", "password"]
    for field in required:
        if not is_non_empty_string(data.get(field)):
            return f"'{field}' is required and must be a non-empty string."

    if not is_valid_email(data["email"]):
        return "Invalid email address format."

    if len(data["password"]) < 6:
        return "Password must be at least 6 characters."

    role = data.get("role", "teacher")
    if not is_valid_role(role):
        return f"Invalid role '{role}'. Must be 'teacher' or 'admin'."

    return None


def validate_login_payload(data: dict) -> Optional[str]:
    """Validate /auth/login request body."""
    if not data:
        return "Request body is required."
    if not is_non_empty_string(data.get("username")):
        return "'username' is required."
    if not is_non_empty_string(data.get("password")):
        return "'password' is required."
    return None


# ── Sign / vocabulary validators ─────────────────────────────────────────────

def validate_sign_payload(data: dict) -> Optional[str]:
    """Validate the sign creation payload."""
    if not data:
        return "Request body is required."
    if not is_non_empty_string(data.get("label")):
        return "'label' is required."
    return None


def validate_review_payload(data: dict) -> Optional[str]:
    """Validate a peer-review decision payload."""
    if not data:
        return "Request body is required."
    decision = data.get("decision")
    if decision not in ("approved", "rejected"):
        return "'decision' must be 'approved' or 'rejected'."
    if decision == "rejected" and not is_non_empty_string(data.get("rejection_reason")):
        return "'rejection_reason' is required when rejecting a sign."
    return None


# ── Annotation validators ────────────────────────────────────────────────────

def validate_annotation_payload(data: dict) -> Optional[str]:
    """Validate an annotation creation payload."""
    if not data:
        return "Request body is required."
    if "recording_id" not in data:
        return "'recording_id' is required."
    if "is_correct" not in data:
        return "'is_correct' is required (true/false)."
    if not data.get("is_correct") and not is_non_empty_string(data.get("correct_label")):
        return "'correct_label' is required when marking as incorrect."
    return None


# ── Assignment validators ─────────────────────────────────────────────────────

def validate_assignment_payload(data: dict) -> Optional[str]:
    """Validate assignment creation payload."""
    if not data:
        return "Request body is required."
    if not is_non_empty_string(data.get("title")):
        return "'title' is required."
    sign_labels = data.get("sign_labels")
    if not isinstance(sign_labels, list) or len(sign_labels) == 0:
        return "'sign_labels' must be a non-empty list of strings."
    return None


# ── File upload validators ────────────────────────────────────────────────────

def is_allowed_video(filename: str) -> bool:
    """Return True if the file extension is in the allowed video set."""
    ext = Path(filename).suffix.lstrip(".").lower()
    return ext in cfg.ALLOWED_VIDEO_EXTENSIONS


def is_allowed_image(filename: str) -> bool:
    """Return True if the file extension is in the allowed image set."""
    ext = Path(filename).suffix.lstrip(".").lower()
    return ext in cfg.ALLOWED_IMAGE_EXTENSIONS


def sanitize_filename(filename: str) -> str:
    """Remove potentially dangerous characters from uploaded filenames."""
    # Keep only alphanumeric, dots, hyphens, underscores
    clean = re.sub(r"[^\w\.\-]", "_", Path(filename).name)
    return clean[:200]  # limit length

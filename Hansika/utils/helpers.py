"""
utils/helpers.py
================
General-purpose utility functions used across the Hansika backend.

Research Component: SLSL Recognition System — Objective 4
Author: Hansika
"""

import json
import uuid
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from flask import jsonify


# ── API Response Helpers ──────────────────────────────────────────────────────

def success_response(data: Any = None, message: str = "Success", status_code: int = 200):
    """
    Standard success JSON response envelope.

    Returns:
        Flask Response with shape:
        { "success": true, "message": "...", "data": ... }
    """
    payload = {"success": True, "message": message}
    if data is not None:
        payload["data"] = data
    return jsonify(payload), status_code


def error_response(message: str, status_code: int = 400, details: Any = None):
    """
    Standard error JSON response envelope.

    Returns:
        Flask Response with shape:
        { "success": false, "message": "...", "details": ... }
    """
    payload = {"success": False, "message": message}
    if details is not None:
        payload["details"] = details
    return jsonify(payload), status_code


def paginated_response(
    items: list,
    total: int,
    page: int,
    per_page: int,
    message: str = "Success",
):
    """Wrap a list result with pagination metadata."""
    return jsonify({
        "success": True,
        "message": message,
        "data": items,
        "pagination": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": max(1, -(-total // per_page)),  # ceiling division
        },
    }), 200


# ── ID & Filename Generators ──────────────────────────────────────────────────

def generate_unique_filename(original_name: str, prefix: str = "") -> str:
    """
    Generate a collision-resistant filename while preserving the extension.

    Example:
        generate_unique_filename("hello.mp4", "sign")
        → "sign_3f4a1b2c.mp4"
    """
    ext = Path(original_name).suffix
    uid = uuid.uuid4().hex[:8]
    ts  = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    parts = filter(None, [prefix, ts, uid])
    return "_".join(parts) + ext


def generate_uuid() -> str:
    """Return a random UUID4 string."""
    return str(uuid.uuid4())


# ── JSON Helpers ──────────────────────────────────────────────────────────────

def safe_json_loads(value: Optional[str], default=None):
    """
    Safely parse a JSON string from the database.
    Returns `default` on any parse failure.
    """
    if not value:
        return default if default is not None else []
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default if default is not None else []


def safe_json_dumps(value) -> str:
    """Safely serialize a value to JSON string (for DB storage)."""
    try:
        return json.dumps(value)
    except (TypeError, ValueError):
        return "[]"


# ── Date Helpers ──────────────────────────────────────────────────────────────

def utcnow_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.utcnow().isoformat()


def format_datetime(dt_str: Optional[str]) -> Optional[str]:
    """Reformat a stored datetime string to a human-readable form."""
    if not dt_str:
        return None
    try:
        dt = datetime.fromisoformat(dt_str)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except ValueError:
        return dt_str


# ── Hashing ───────────────────────────────────────────────────────────────────

def sha256_file(file_path: str) -> str:
    """Return the SHA-256 hex digest of a file (for integrity checking)."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# ── Pagination ────────────────────────────────────────────────────────────────

def parse_pagination(args: dict, default_per_page: int = 20) -> tuple:
    """
    Extract and clamp pagination parameters from query string.

    Returns:
        (page, per_page, offset) all as integers.
    """
    try:
        page = max(1, int(args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        per_page = max(1, min(int(args.get("per_page", default_per_page)), 100))
    except (TypeError, ValueError):
        per_page = default_per_page
    offset = (page - 1) * per_page
    return page, per_page, offset

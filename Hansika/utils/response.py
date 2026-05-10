"""
utils/response.py
=================
Standardized API JSON responses for success and error cases.

Research Component: SLSL Recognition System — Objective 4
"""

from typing import Any, Optional
from flask import jsonify

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
        { "success": false, "error": "...", "details": ... }
    """
    payload = {"success": False, "error": message}
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
            "pages": max(1, -(-total // per_page)) if per_page > 0 else 1,  # ceiling division
        },
    }), 200

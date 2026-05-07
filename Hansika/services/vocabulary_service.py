"""
services/vocabulary_service.py
================================
Vocabulary / sign management service.

Handles creation, listing, retrieval, and status management
of sign entries submitted by teachers.

Research Component: SLSL Recognition System — Objective 4
Author: Hansika
"""

import logging
from pathlib import Path
from typing import Optional, Tuple

from database.db import db_context, row_to_dict, rows_to_list
from database.models import SignModel
from utils.helpers import utcnow_iso, safe_json_loads

logger = logging.getLogger(__name__)


# ── Create ────────────────────────────────────────────────────────────────────

def create_sign(
    label: str,
    submitted_by: int,
    description: str = "",
    video_path: str = "",
    keypoints_path: str = "",
) -> Tuple[bool, str, Optional[dict]]:
    """
    Create a new pending sign entry.

    Returns:
        (success, message, sign_dict)
    """
    try:
        payload = SignModel.create_payload(
            label=label,
            submitted_by=submitted_by,
            description=description,
            video_path=video_path,
            keypoints_path=keypoints_path,
        )
        with db_context() as conn:
            cursor = conn.execute(
                """INSERT INTO signs
                   (label, description, video_path, keypoints_path,
                    submitted_by, status, sample_count, is_in_model, created_at, updated_at)
                   VALUES
                   (:label, :description, :video_path, :keypoints_path,
                    :submitted_by, :status, :sample_count, :is_in_model, :created_at, :updated_at)""",
                payload,
            )
            sign = row_to_dict(
                conn.execute("SELECT * FROM signs WHERE id = ?", (cursor.lastrowid,)).fetchone()
            )
        return True, "Sign submitted for peer review.", sign
    except Exception as exc:
        logger.exception("create_sign failed for label='%s': %s", label, exc)
        return False, f"Failed to create sign: {exc}", None


# ── Read ──────────────────────────────────────────────────────────────────────

def get_sign(sign_id: int) -> Optional[dict]:
    """Return a single sign by ID or None."""
    try:
        with db_context() as conn:
            row = conn.execute("SELECT * FROM signs WHERE id = ?", (sign_id,)).fetchone()
        return row_to_dict(row) if row else None
    except Exception as exc:
        logger.exception("get_sign(%s) failed: %s", sign_id, exc)
        return None


def list_signs(
    status: Optional[str] = None,
    submitted_by: Optional[int] = None,
    page: int = 1,
    per_page: int = 20,
) -> Tuple[list, int]:
    """
    List signs with optional filters and pagination.

    Returns:
        (signs_list, total_count)
    """
    try:
        clauses = []
        params  = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if submitted_by is not None:
            clauses.append("submitted_by = ?")
            params.append(submitted_by)

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        offset = (page - 1) * per_page

        with db_context() as conn:
            total = conn.execute(
                f"SELECT COUNT(*) FROM signs {where}", params
            ).fetchone()[0]
            rows = conn.execute(
                f"SELECT * FROM signs {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                params + [per_page, offset],
            ).fetchall()
        return rows_to_list(rows), total
    except Exception as exc:
        logger.exception("list_signs failed: %s", exc)
        return [], 0


def get_pending_signs() -> list:
    """Return all pending signs awaiting peer review."""
    items, _ = list_signs(status=SignModel.STATUS_PENDING, per_page=200)
    return items


def get_approved_signs() -> list:
    """Return all approved signs visible to students."""
    items, _ = list_signs(status=SignModel.STATUS_APPROVED, per_page=500)
    return items


# ── Status updates ────────────────────────────────────────────────────────────

def update_sign_status(sign_id: int, status: str) -> bool:
    """Set a sign's status field (called by peer review service)."""
    try:
        with db_context() as conn:
            conn.execute(
                "UPDATE signs SET status = ?, updated_at = ? WHERE id = ?",
                (status, utcnow_iso(), sign_id),
            )
        return True
    except Exception as exc:
        logger.exception("update_sign_status(%s, %s) failed: %s", sign_id, status, exc)
        return False


def update_sign_keypoints_path(sign_id: int, path: str, sample_count: int = 0) -> bool:
    """Update the keypoints file path after extraction."""
    try:
        with db_context() as conn:
            conn.execute(
                "UPDATE signs SET keypoints_path = ?, sample_count = ?, updated_at = ? WHERE id = ?",
                (path, sample_count, utcnow_iso(), sign_id),
            )
        return True
    except Exception as exc:
        logger.exception("update_sign_keypoints_path failed: %s", exc)
        return False


def mark_sign_in_model(sign_id: int, in_model: bool = True) -> bool:
    """Mark whether a sign has been included in the active TFLite model."""
    try:
        with db_context() as conn:
            conn.execute(
                "UPDATE signs SET is_in_model = ?, updated_at = ? WHERE id = ?",
                (1 if in_model else 0, utcnow_iso(), sign_id),
            )
        return True
    except Exception as exc:
        logger.exception("mark_sign_in_model failed: %s", exc)
        return False


# ── Stats ─────────────────────────────────────────────────────────────────────

def get_vocabulary_stats() -> dict:
    """Return aggregate counts by status."""
    try:
        with db_context() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) as cnt FROM signs GROUP BY status"
            ).fetchall()
            in_model = conn.execute(
                "SELECT COUNT(*) FROM signs WHERE is_in_model = 1"
            ).fetchone()[0]
        counts = {r["status"]: r["cnt"] for r in rows}
        counts["in_model"] = in_model
        return counts
    except Exception as exc:
        logger.exception("get_vocabulary_stats failed: %s", exc)
        return {}

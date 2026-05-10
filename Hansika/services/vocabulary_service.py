"""
services/vocabulary_service.py
================================
Vocabulary / sign management service.
Now using MongoDB via SignRepository.

Research Component: SLSL Recognition System — Objective 4
"""

import logging
from typing import Optional, Tuple
from datetime import datetime

from repositories.sign_repository import SignRepository

logger = logging.getLogger(__name__)

# ── Create ────────────────────────────────────────────────────────────────────

def create_sign(
    label: str,
    submitted_by: str,
    description: str = "",
    video_path: str = "",
    keypoints_path: str = "",
) -> Tuple[bool, str, Optional[dict]]:
    try:
        now = datetime.utcnow().isoformat()
        payload = {
            "label": label,
            "description": description,
            "video_path": video_path,
            "keypoints_path": keypoints_path,
            "submitted_by": submitted_by,
            "status": SignRepository.STATUS_PENDING,
            "sample_count": 0,
            "is_in_model": 0,
            "created_at": now,
            "updated_at": now,
        }
        sign = SignRepository.create_sign(payload)
        return True, "Sign submitted for peer review.", sign
    except Exception as exc:
        logger.exception("create_sign failed for label='%s': %s", label, exc)
        return False, f"Failed to create sign: {exc}", None

# ── Read ──────────────────────────────────────────────────────────────────────

def get_sign(sign_id: str) -> Optional[dict]:
    try:
        return SignRepository.get_by_id(sign_id)
    except Exception as exc:
        logger.exception("get_sign(%s) failed: %s", sign_id, exc)
        return None

def list_signs(
    status: Optional[str] = None,
    submitted_by: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
) -> Tuple[list, int]:
    try:
        return SignRepository.list_signs(status, submitted_by, page, per_page)
    except Exception as exc:
        logger.exception("list_signs failed: %s", exc)
        return [], 0

def get_pending_signs() -> list:
    items, _ = list_signs(status=SignRepository.STATUS_PENDING, per_page=200)
    return items

def get_approved_signs() -> list:
    items, _ = list_signs(status=SignRepository.STATUS_APPROVED, per_page=500)
    return items

# ── Status updates ────────────────────────────────────────────────────────────

def update_sign_status(sign_id: str, status: str) -> bool:
    try:
        return SignRepository.update_status(sign_id, status, datetime.utcnow().isoformat())
    except Exception as exc:
        logger.exception("update_sign_status(%s, %s) failed: %s", sign_id, status, exc)
        return False

def update_sign_keypoints_path(sign_id: str, path: str, sample_count: int = 0) -> bool:
    try:
        return SignRepository.update_keypoints(sign_id, path, sample_count, datetime.utcnow().isoformat())
    except Exception as exc:
        logger.exception("update_sign_keypoints_path failed: %s", exc)
        return False

def mark_sign_in_model(sign_id: str, in_model: bool = True) -> bool:
    try:
        return SignRepository.mark_in_model(sign_id, in_model, datetime.utcnow().isoformat())
    except Exception as exc:
        logger.exception("mark_sign_in_model failed: %s", exc)
        return False

# ── Stats ─────────────────────────────────────────────────────────────────────

def get_vocabulary_stats() -> dict:
    try:
        return SignRepository.get_stats()
    except Exception as exc:
        logger.exception("get_vocabulary_stats failed: %s", exc)
        return {}

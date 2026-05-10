"""
services/review_service.py
================================
Peer review workflow service.
Now using MongoDB via ReviewRepository.

Research Component: SLSL Recognition System — Objective 4
"""

import logging
from typing import Optional, Tuple
from datetime import datetime

from repositories.review_repository import ReviewRepository
from repositories.sign_repository import SignRepository
from database.collections import get_signs_collection, get_peer_reviews_collection
from utils.bson_helper import object_id_to_str, str_to_object_id

logger = logging.getLogger(__name__)


def submit_review(
    sign_id: str,
    reviewer_id: str,
    decision: str,
    rejection_reason: str = "",
    notes: str = "",
) -> Tuple[bool, str, Optional[dict]]:
    try:
        sign = SignRepository.get_by_id(sign_id)
        if not sign:
            return False, f"Sign #{sign_id} not found.", None

        if sign.get("submitted_by") == reviewer_id:
            return False, "You cannot review your own sign submission.", None

        # Check duplicate
        coll = get_peer_reviews_collection()
        duplicate = coll.find_one({"sign_id": sign_id, "reviewer_id": reviewer_id})
        if duplicate:
            return False, "You have already reviewed this sign.", None

        payload = {
            "sign_id": sign_id,
            "reviewer_id": reviewer_id,
            "decision": decision,
            "rejection_reason": rejection_reason,
            "notes": notes,
            "reviewed_at": datetime.utcnow().isoformat(),
        }
        review = ReviewRepository.create_review(payload)

        new_status = (
            SignRepository.STATUS_APPROVED
            if decision == ReviewRepository.DECISION_APPROVED
            else SignRepository.STATUS_REJECTED
        )
        SignRepository.update_status(sign_id, new_status, datetime.utcnow().isoformat())

        logger.info("Peer review: sign#%s %s by user#%s", sign_id, decision, reviewer_id)
        return True, f"Sign {decision} successfully.", review

    except Exception as exc:
        logger.exception("submit_review failed: %s", exc)
        return False, f"Review submission failed: {exc}", None


def get_reviews_for_sign(sign_id: str) -> list:
    try:
        return ReviewRepository.list_reviews_for_sign(sign_id)
    except Exception as exc:
        logger.exception("get_reviews_for_sign(%s) failed: %s", sign_id, exc)
        return []


def get_pending_review_queue(reviewer_id: str) -> list:
    try:
        signs_coll = get_signs_collection()
        reviews_coll = get_peer_reviews_collection()
        
        # Signs already reviewed by this reviewer
        reviewed_signs = [r["sign_id"] for r in reviews_coll.find({"reviewer_id": reviewer_id}, {"sign_id": 1})]
        
        query = {
            "status": "pending",
            "submitted_by": {"$ne": reviewer_id},
            "_id": {"$nin": [str_to_object_id(sid) for sid in reviewed_signs if str_to_object_id(sid)]}
        }
        
        cursor = signs_coll.find(query).sort("created_at", 1)
        return [object_id_to_str(doc) for doc in cursor]
    except Exception as exc:
        logger.exception("get_pending_review_queue failed: %s", exc)
        return []


def get_review_statistics() -> dict:
    try:
        coll = get_peer_reviews_collection()
        total = coll.count_documents({})
        approved = coll.count_documents({"decision": "approved"})
        rejected = coll.count_documents({"decision": "rejected"})
        
        return {
            "total_reviews": total,
            "approved": approved,
            "rejected": rejected,
            "approval_rate": round(approved / total * 100, 1) if total else 0.0,
        }
    except Exception as exc:
        logger.exception("get_review_statistics failed: %s", exc)
        return {}

"""
services/peer_review_service.py
================================
Peer review workflow service.

Teacher A submits a sign; Teacher B reviews it (approve/reject).
Only approved signs move into the training pipeline.

Research Component: SLSL Recognition System — Objective 4
Author: Hansika
"""

import logging
from typing import Optional, Tuple

from database.db import db_context, row_to_dict, rows_to_list
from database.models import PeerReviewModel, SignModel
from services.vocabulary_service import update_sign_status
from utils.helpers import utcnow_iso

logger = logging.getLogger(__name__)


def submit_review(
    sign_id: int,
    reviewer_id: int,
    decision: str,
    rejection_reason: str = "",
    notes: str = "",
) -> Tuple[bool, str, Optional[dict]]:
    """
    Submit a peer review decision for a sign.

    Business rules:
    - A teacher cannot review their own sign.
    - A sign can only be reviewed once per reviewer.
    - Approved signs transition to 'approved' status.
    - Rejected signs transition to 'rejected' status.

    Args:
        sign_id:          ID of the sign being reviewed.
        reviewer_id:      ID of the reviewing teacher.
        decision:         'approved' or 'rejected'.
        rejection_reason: Required when decision == 'rejected'.
        notes:            Optional free-text reviewer notes.

    Returns:
        (success, message, review_dict)
    """
    try:
        with db_context() as conn:
            # Fetch the sign
            sign = conn.execute(
                "SELECT * FROM signs WHERE id = ?", (sign_id,)
            ).fetchone()
            if not sign:
                return False, f"Sign #{sign_id} not found.", None
            sign = dict(sign)

            # Self-review prevention
            if sign["submitted_by"] == reviewer_id:
                return False, "You cannot review your own sign submission.", None

            # Prevent duplicate reviews
            duplicate = conn.execute(
                "SELECT id FROM peer_reviews WHERE sign_id = ? AND reviewer_id = ?",
                (sign_id, reviewer_id),
            ).fetchone()
            if duplicate:
                return False, "You have already reviewed this sign.", None

            # Insert review record
            payload = PeerReviewModel.create_payload(
                sign_id=sign_id,
                reviewer_id=reviewer_id,
                decision=decision,
                rejection_reason=rejection_reason,
                notes=notes,
            )
            cursor = conn.execute(
                """INSERT INTO peer_reviews
                   (sign_id, reviewer_id, decision, rejection_reason, notes, reviewed_at)
                   VALUES (:sign_id, :reviewer_id, :decision, :rejection_reason, :notes, :reviewed_at)""",
                payload,
            )
            review_id = cursor.lastrowid

            # Update sign status
            new_status = (
                SignModel.STATUS_APPROVED
                if decision == PeerReviewModel.DECISION_APPROVED
                else SignModel.STATUS_REJECTED
            )
            conn.execute(
                "UPDATE signs SET status = ?, updated_at = ? WHERE id = ?",
                (new_status, utcnow_iso(), sign_id),
            )

            review = row_to_dict(
                conn.execute(
                    "SELECT * FROM peer_reviews WHERE id = ?", (review_id,)
                ).fetchone()
            )

        logger.info(
            "Peer review: sign#%s %s by user#%s", sign_id, decision, reviewer_id
        )
        return True, f"Sign {decision} successfully.", review

    except Exception as exc:
        logger.exception("submit_review failed: %s", exc)
        return False, f"Review submission failed: {exc}", None


def get_reviews_for_sign(sign_id: int) -> list:
    """Return all reviews for a specific sign."""
    try:
        with db_context() as conn:
            rows = conn.execute(
                """SELECT pr.*, u.username as reviewer_name
                   FROM peer_reviews pr
                   JOIN users u ON pr.reviewer_id = u.id
                   WHERE pr.sign_id = ?
                   ORDER BY pr.reviewed_at DESC""",
                (sign_id,),
            ).fetchall()
        return rows_to_list(rows)
    except Exception as exc:
        logger.exception("get_reviews_for_sign(%s) failed: %s", sign_id, exc)
        return []


def get_pending_review_queue(reviewer_id: int) -> list:
    """
    Return signs pending review that were NOT submitted by the current reviewer.
    Signs the reviewer already reviewed are excluded.
    """
    try:
        with db_context() as conn:
            rows = conn.execute(
                """SELECT s.*, u.username as submitter_name
                   FROM signs s
                   JOIN users u ON s.submitted_by = u.id
                   WHERE s.status = 'pending'
                     AND s.submitted_by != ?
                     AND s.id NOT IN (
                         SELECT sign_id FROM peer_reviews WHERE reviewer_id = ?
                     )
                   ORDER BY s.created_at ASC""",
                (reviewer_id, reviewer_id),
            ).fetchall()
        return rows_to_list(rows)
    except Exception as exc:
        logger.exception("get_pending_review_queue failed: %s", exc)
        return []


def get_review_statistics() -> dict:
    """Return aggregate review statistics."""
    try:
        with db_context() as conn:
            total    = conn.execute("SELECT COUNT(*) FROM peer_reviews").fetchone()[0]
            approved = conn.execute(
                "SELECT COUNT(*) FROM peer_reviews WHERE decision = 'approved'"
            ).fetchone()[0]
            rejected = conn.execute(
                "SELECT COUNT(*) FROM peer_reviews WHERE decision = 'rejected'"
            ).fetchone()[0]
        return {
            "total_reviews": total,
            "approved": approved,
            "rejected": rejected,
            "approval_rate": round(approved / total * 100, 1) if total else 0.0,
        }
    except Exception as exc:
        logger.exception("get_review_statistics failed: %s", exc)
        return {}

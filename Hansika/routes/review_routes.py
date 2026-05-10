"""
routes/review_routes.py
========================
Peer review workflow endpoints.

Research Component: SLSL Recognition System — Objective 4
Author: Hansika
"""

import logging
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from services.peer_review_service import (
    submit_review,
    get_reviews_for_sign,
    get_pending_review_queue,
    get_review_statistics,
)
from utils.response import success_response, error_response
from utils.validators import validate_review_payload

logger = logging.getLogger(__name__)

review_bp = Blueprint("review", __name__, url_prefix="/api/signs")


@review_bp.route("/review", methods=["POST"])
@jwt_required()
def post_review():
    """
    POST /api/signs/review
    Submit a peer review decision for a sign.

    Body: { sign_id, decision, rejection_reason?, notes? }
    """
    user_id = get_jwt_identity()
    data = request.get_json(silent=True)
    err = validate_review_payload(data)
    if err:
        return error_response(err, 400)

    sign_id = data.get("sign_id")
    if not sign_id:
        return error_response("'sign_id' is required.", 400)

    success, message, review = submit_review(
        sign_id=sign_id,
        reviewer_id=user_id,
        decision=data["decision"],
        rejection_reason=data.get("rejection_reason", ""),
        notes=data.get("notes", ""),
    )
    if not success:
        return error_response(message, 400)
    return success_response(review, message, 201)


@review_bp.route("/<string:sign_id>/reviews", methods=["GET"])
@jwt_required()
def sign_reviews(sign_id):
    """
    GET /api/signs/<id>/reviews
    Get all peer reviews for a specific sign.
    """
    reviews = get_reviews_for_sign(sign_id)
    return success_response(reviews)


@review_bp.route("/review/queue", methods=["GET"])
@jwt_required()
def review_queue():
    """
    GET /api/signs/review/queue
    Return signs the current teacher can review (excludes own and already reviewed).
    """
    user_id = int(get_jwt_identity())
    queue = get_pending_review_queue(user_id)
    return success_response(queue)


@review_bp.route("/review/stats", methods=["GET"])
@jwt_required()
def review_stats():
    """GET /api/signs/review/stats — Aggregate review statistics."""
    return success_response(get_review_statistics())

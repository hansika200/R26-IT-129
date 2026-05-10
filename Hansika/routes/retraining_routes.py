"""
routes/retraining_routes.py
===========================
Retraining endpoints for the teacher dashboard.

Research Component: SLSL Recognition System — Objective 4
"""

import logging
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from services.retraining_service import (
    check_retrain_eligibility,
    trigger_retraining,
    list_retraining_logs,
)
from utils.response import success_response, error_response
from utils.helpers import parse_pagination

logger = logging.getLogger(__name__)

retraining_bp = Blueprint("retraining", __name__, url_prefix="/api/retraining")


@retraining_bp.route("/check", methods=["GET"])
@jwt_required()
def check_retrain():
    """GET /api/retraining/check — Check if retraining threshold is met."""
    return success_response(check_retrain_eligibility())


@retraining_bp.route("/start", methods=["POST"])
@jwt_required()
def start_retraining():
    """
    POST /api/retraining/start
    Manually trigger AI retraining.
    Body: { reason? }  (optional override reason)
    """
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}
    reason = data.get("reason", "manual")

    success, message, log = trigger_retraining(triggered_by=user_id, reason=reason)
    if not success:
        return error_response(message, 500)
    return success_response(log, message)


@retraining_bp.route("/logs", methods=["GET"])
@jwt_required()
def retrain_logs():
    """GET /api/retraining/logs — Paginated retraining history."""
    page, per_page, _ = parse_pagination(request.args)
    logs, total = list_retraining_logs(page=page, per_page=per_page)
    return success_response({"logs": logs, "total": total, "page": page})

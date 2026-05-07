"""
routes/analytics_routes.py
============================
Analytics and retraining endpoints for the teacher dashboard.

Research Component: SLSL Recognition System — Objective 4
Author: Hansika
"""

import logging
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from services.analytics_service import (
    get_dashboard_summary,
    get_student_performance_overview,
    get_struggling_students,
    get_sign_difficulty_report,
    get_activity_trend,
    get_assignment_completion_report,
)
from services.retraining_service import (
    check_retrain_eligibility,
    trigger_retraining,
    list_retraining_logs,
)
from ml_integration.tflite_updater import get_active_model_info, list_model_backups
from ml_integration.dataset_generator import export_approved_signs_dataset, export_annotated_student_dataset
from database.models import RetrainingLogModel
from config.settings import get_config
from utils.helpers import success_response, error_response, parse_pagination

logger = logging.getLogger(__name__)
cfg = get_config()

analytics_bp = Blueprint("analytics", __name__, url_prefix="/api")


# ── Dashboard ─────────────────────────────────────────────────────────────────

@analytics_bp.route("/analytics/dashboard", methods=["GET"])
@jwt_required()
def dashboard():
    """GET /api/analytics/dashboard — Teacher dashboard summary."""
    return success_response(get_dashboard_summary())


@analytics_bp.route("/analytics/students", methods=["GET"])
@jwt_required()
def student_overview():
    """GET /api/analytics/students?assignment_id=X — Per-student performance."""
    assignment_id = request.args.get("assignment_id", type=int)
    data = get_student_performance_overview(assignment_id)
    return success_response(data)


@analytics_bp.route("/analytics/struggling", methods=["GET"])
@jwt_required()
def struggling():
    """GET /api/analytics/struggling?threshold=50 — Students below score threshold."""
    threshold = request.args.get("threshold", 50.0, type=float)
    return success_response(get_struggling_students(threshold))


@analytics_bp.route("/analytics/sign-difficulty", methods=["GET"])
@jwt_required()
def sign_difficulty():
    """GET /api/analytics/sign-difficulty — Signs with highest error rates."""
    return success_response(get_sign_difficulty_report())


@analytics_bp.route("/analytics/activity", methods=["GET"])
@jwt_required()
def activity_trend():
    """GET /api/analytics/activity?days=30 — Daily activity trend."""
    days = request.args.get("days", 30, type=int)
    return success_response(get_activity_trend(days))


@analytics_bp.route("/analytics/assignments", methods=["GET"])
@jwt_required()
def assignment_report():
    """GET /api/analytics/assignments — Per-assignment completion overview."""
    return success_response(get_assignment_completion_report())


# ── Retraining ────────────────────────────────────────────────────────────────

@analytics_bp.route("/retraining/check", methods=["GET"])
@jwt_required()
def check_retrain():
    """GET /api/retraining/check — Check if retraining threshold is met."""
    return success_response(check_retrain_eligibility())


@analytics_bp.route("/retraining/start", methods=["POST"])
@jwt_required()
def start_retraining():
    """
    POST /api/retraining/start
    Manually trigger AI retraining.
    Body: { reason? }  (optional override reason)
    """
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    reason = data.get("reason", RetrainingLogModel.REASON_MANUAL)

    success, message, log = trigger_retraining(triggered_by=user_id, reason=reason)
    if not success:
        return error_response(message, 500)
    return success_response(log, message)


@analytics_bp.route("/retraining/logs", methods=["GET"])
@jwt_required()
def retrain_logs():
    """GET /api/retraining/logs — Paginated retraining history."""
    page, per_page, _ = parse_pagination(request.args)
    logs, total = list_retraining_logs(page=page, per_page=per_page)
    return success_response({"logs": logs, "total": total, "page": page})


# ── Model info ────────────────────────────────────────────────────────────────

@analytics_bp.route("/model/info", methods=["GET"])
@jwt_required()
def model_info():
    """GET /api/model/info — Active TFLite model metadata."""
    return success_response(get_active_model_info())


@analytics_bp.route("/model/backups", methods=["GET"])
@jwt_required()
def model_backups():
    """GET /api/model/backups — List of backed-up model files."""
    return success_response(list_model_backups())


# ── Dataset export ────────────────────────────────────────────────────────────

@analytics_bp.route("/dataset/export/signs", methods=["POST"])
@jwt_required()
def export_signs_dataset():
    """POST /api/dataset/export/signs — Export approved signs as X/Y numpy arrays."""
    import os
    from config.settings import get_config as _cfg
    out_dir = str(_cfg().APPROVED_SIGNS_DIR)
    ok, message, stats = export_approved_signs_dataset(out_dir)
    if not ok:
        return error_response(message, 500)
    return success_response(stats, message)


@analytics_bp.route("/dataset/export/students", methods=["POST"])
@jwt_required()
def export_student_dataset():
    """POST /api/dataset/export/students — Export annotated student recordings."""
    out_dir = cfg.ANNOTATIONS_DIR
    ok, message, stats = export_annotated_student_dataset(out_dir)
    if not ok:
        return error_response(message, 500)
    return success_response(stats, message)

"""
routes/analytics_routes.py
============================
Analytics endpoints for the teacher dashboard.

Research Component: SLSL Recognition System — Objective 4
"""

import logging
from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from services.analytics_service import (
    get_dashboard_summary,
    get_student_performance_overview,
    get_struggling_students,
    get_sign_difficulty_report,
    get_activity_trend,
    get_assignment_completion_report,
)
from ml_integration.tflite_updater import get_active_model_info, list_model_backups
from ml_integration.dataset_generator import export_approved_signs_dataset, export_annotated_student_dataset
from config.settings import get_config
from utils.response import success_response, error_response

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
    assignment_id = request.args.get("assignment_id")
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
    out_dir = str(cfg.APPROVED_SIGNS_DIR)
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

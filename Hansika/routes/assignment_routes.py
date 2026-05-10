"""
routes/assignment_routes.py
=============================
Assignment management and student progress endpoints.

Research Component: SLSL Recognition System — Objective 4
Author: Hansika
"""

import logging
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from services.assignment_service import (
    create_assignment, get_assignment, list_assignments,
    deactivate_assignment, upsert_student_progress,
    get_student_progress, get_all_progress_for_assignment,
)
from utils.response import success_response, error_response
from utils.helpers import parse_pagination
from utils.validators import validate_assignment_payload

logger = logging.getLogger(__name__)

assignment_bp = Blueprint("assignment", __name__, url_prefix="/api/assignments")


@assignment_bp.route("/create", methods=["POST"])
@jwt_required()
def create():
    """
    POST /api/assignments/create
    Create a new sign-practice assignment.

    Body: { title, sign_labels[], description?, due_date? }
    """
    user_id = get_jwt_identity()
    data = request.get_json(silent=True)
    err = validate_assignment_payload(data)
    if err:
        return error_response(err, 400)

    success, message, assignment = create_assignment(
        title=data["title"],
        created_by=user_id,
        sign_labels=data["sign_labels"],
        description=data.get("description", ""),
        due_date=data.get("due_date"),
    )
    if not success:
        return error_response(message, 500)
    return success_response(assignment, message, 201)


@assignment_bp.route("/", methods=["GET"])
@jwt_required()
def list_all():
    """GET /api/assignments/?page=1 — List all active assignments."""
    page, per_page, _ = parse_pagination(request.args)
    assignments, total = list_assignments(is_active=True, page=page, per_page=per_page)
    return success_response({"assignments": assignments, "total": total, "page": page})


@assignment_bp.route("/<string:assignment_id>", methods=["GET"])
@jwt_required()
def get_detail(assignment_id):
    """GET /api/assignments/<id> — Single assignment detail."""
    a = get_assignment(assignment_id)
    if not a:
        return error_response(f"Assignment #{assignment_id} not found.", 404)
    return success_response(a)


@assignment_bp.route("/<string:assignment_id>/deactivate", methods=["POST"])
@jwt_required()
def deactivate(assignment_id):
    """POST /api/assignments/<id>/deactivate — Soft-delete an assignment."""
    ok = deactivate_assignment(assignment_id)
    if not ok:
        return error_response("Failed to deactivate assignment.", 500)
    return success_response({"assignment_id": assignment_id}, "Assignment deactivated.")


@assignment_bp.route("/<string:assignment_id>/progress", methods=["GET"])
@jwt_required()
def all_progress(assignment_id):
    """GET /api/assignments/<id>/progress — All students' progress."""
    progress = get_all_progress_for_assignment(assignment_id)
    return success_response(progress)


@assignment_bp.route("/progress/update", methods=["POST"])
@jwt_required()
def update_progress():
    """
    POST /api/assignments/progress/update
    Record a student's attempt at a sign within an assignment.

    Body: { student_id, assignment_id, sign_label, is_correct }
    """
    data = request.get_json(silent=True)
    if not data:
        return error_response("Request body required.", 400)
    ok, message = upsert_student_progress(
        student_id=data.get("student_id", ""),
        assignment_id=str(data.get("assignment_id", "")),
        sign_label=data.get("sign_label", ""),
        is_correct=bool(data.get("is_correct", False)),
    )
    if not ok:
        return error_response(message, 400)
    return success_response(None, message)


@assignment_bp.route("/progress/<student_id>/<string:assignment_id>", methods=["GET"])
@jwt_required()
def student_progress(student_id, assignment_id):
    """GET /api/assignments/progress/<student_id>/<assignment_id>"""
    p = get_student_progress(student_id, assignment_id)
    if not p:
        return error_response("No progress record found.", 404)
    return success_response(p)

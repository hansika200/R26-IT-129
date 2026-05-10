"""
routes/annotation_routes.py
=============================
Annotation workflow endpoints.

Research Component: SLSL Recognition System — Objective 4
Author: Hansika
"""

import logging
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from services.annotation_service import (
    ingest_student_recording,
    list_pending_recordings,
    create_annotation,
    list_annotations,
    get_annotation_stats,
    get_annotation_export_data,
    mark_annotations_exported,
)
from utils.response import success_response, error_response
from utils.helpers import parse_pagination
from utils.validators import validate_annotation_payload

logger = logging.getLogger(__name__)

annotation_bp = Blueprint("annotation", __name__, url_prefix="/api/annotations")


@annotation_bp.route("/recordings/ingest", methods=["POST"])
@jwt_required()
def ingest_recording():
    """
    POST /api/annotations/recordings/ingest
    Save a student recording for annotation.
    Called by the Flutter app or Janith server bridge.

    Body: { student_id, sign_label, video_path?, keypoints_path?,
            prediction?, confidence? }
    """
    data = request.get_json(silent=True)
    if not data:
        return error_response("Request body required.", 400)

    success, message, rec = ingest_student_recording(
        student_id=data.get("student_id", ""),
        sign_label=data.get("sign_label", ""),
        video_path=data.get("video_path", ""),
        keypoints_path=data.get("keypoints_path", ""),
        prediction=data.get("prediction", ""),
        confidence=float(data.get("confidence", 0.0)),
    )
    if not success:
        return error_response(message, 500)
    return success_response(rec, message, 201)


@annotation_bp.route("/recordings/pending", methods=["GET"])
@jwt_required()
def pending_recordings():
    """GET /api/annotations/recordings/pending — Student recordings awaiting annotation."""
    page, per_page, _ = parse_pagination(request.args)
    recordings, total = list_pending_recordings(page=page, per_page=per_page)
    return success_response({"recordings": recordings, "total": total, "page": page})


@annotation_bp.route("/create", methods=["POST"])
@jwt_required()
def create():
    """
    POST /api/annotations/create
    Annotate a student recording.

    Body: { recording_id, is_correct, correct_label?, notes? }
    """
    user_id = get_jwt_identity()
    data = request.get_json(silent=True)
    err = validate_annotation_payload(data)
    if err:
        return error_response(err, 400)

    success, message, ann = create_annotation(
        recording_id=str(data["recording_id"]),
        annotated_by=user_id,
        is_correct=bool(data["is_correct"]),
        correct_label=data.get("correct_label", ""),
        notes=data.get("notes", ""),
    )
    if not success:
        return error_response(message, 400)
    return success_response(ann, message, 201)


@annotation_bp.route("/", methods=["GET"])
@jwt_required()
def get_annotations():
    """GET /api/annotations/?page=1&per_page=20 — All annotations."""
    page, per_page, _ = parse_pagination(request.args)
    anns, total = list_annotations(page=page, per_page=per_page)
    return success_response({"annotations": anns, "total": total, "page": page})


@annotation_bp.route("/stats", methods=["GET"])
@jwt_required()
def annotation_stats():
    """GET /api/annotations/stats — Annotation aggregate stats."""
    return success_response(get_annotation_stats())


@annotation_bp.route("/export", methods=["GET"])
@jwt_required()
def export_annotations():
    """
    GET /api/annotations/export
    Return annotation data ready for integration into the training pipeline.
    """
    data = get_annotation_export_data()
    return success_response({"annotations": data, "count": len(data)})


@annotation_bp.route("/mark-exported", methods=["POST"])
@jwt_required()
def mark_exported():
    """
    POST /api/annotations/mark-exported
    Body: { annotation_ids: [1, 2, 3] }
    Mark annotations as included in the training dataset.
    """
    data = request.get_json(silent=True)
    ids = data.get("annotation_ids", []) if data else []
    if not isinstance(ids, list):
        return error_response("'annotation_ids' must be a list.", 400)
    ok = mark_annotations_exported(ids)
    if not ok:
        return error_response("Failed to mark annotations.", 500)
    return success_response({"marked": len(ids)}, "Annotations marked as exported.")

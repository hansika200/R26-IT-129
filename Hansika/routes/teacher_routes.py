"""
routes/teacher_routes.py
==========================
Teacher dashboard and sign/vocabulary management endpoints.

Research Component: SLSL Recognition System — Objective 4
Author: Hansika
"""

import logging
import os
from pathlib import Path

from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from services.vocabulary_service import (
    create_sign, get_sign, list_signs,
    get_pending_signs, get_approved_signs,
    get_vocabulary_stats, update_sign_keypoints_path,
)
from services.auth_service import list_users
from ml_integration.keypoint_bridge import extract_keypoints_from_video, load_classes
from config.settings import get_config
from utils.helpers import success_response, error_response, generate_unique_filename, parse_pagination
from utils.validators import validate_sign_payload, is_allowed_video, sanitize_filename

logger = logging.getLogger(__name__)
cfg = get_config()

teacher_bp = Blueprint("teacher", __name__, url_prefix="/api")


# ── Vocabulary Management ────────────────────────────────────────────────────

@teacher_bp.route("/signs/upload", methods=["POST"])
@jwt_required()
def upload_sign():
    """
    POST /api/signs/upload
    Submit a new sign video (multipart/form-data).

    Fields:
        label (str): The sign label
        description (str, optional)
        video (file, optional): Video file upload
    """
    user_id = int(get_jwt_identity())
    label = request.form.get("label", "").strip()
    description = request.form.get("description", "").strip()

    if not label:
        return error_response("'label' is required.", 400)

    video_path = ""
    keypoints_path = ""

    # Handle video file upload
    if "video" in request.files:
        file = request.files["video"]
        if file.filename and is_allowed_video(file.filename):
            safe_name = generate_unique_filename(sanitize_filename(file.filename), prefix=f"sign_{label}")
            dest = Path(cfg.TEACHER_RECORDINGS_DIR) / safe_name
            dest.parent.mkdir(parents=True, exist_ok=True)
            file.save(str(dest))
            video_path = str(dest)
            logger.info("Sign video saved: %s", dest)

            # Extract keypoints from the uploaded video
            npy_name = safe_name.replace(Path(safe_name).suffix, ".npy")
            npy_dest = str(Path(cfg.TEACHER_RECORDINGS_DIR) / "keypoints" / npy_name)
            ok, msg, kp_path = extract_keypoints_from_video(str(dest), npy_dest)
            if ok:
                keypoints_path = kp_path
                logger.info("Keypoints extracted: %s", kp_path)
            else:
                logger.warning("Keypoint extraction failed: %s", msg)

    success, message, sign = create_sign(
        label=label,
        submitted_by=user_id,
        description=description,
        video_path=video_path,
        keypoints_path=keypoints_path,
    )
    if not success:
        return error_response(message, 500)
    return success_response(sign, message, 201)


@teacher_bp.route("/signs", methods=["GET"])
@jwt_required()
def get_signs():
    """
    GET /api/signs?status=pending&page=1&per_page=20
    List signs with optional status filter.
    """
    status = request.args.get("status")
    page, per_page, _ = parse_pagination(request.args)
    signs, total = list_signs(status=status, page=page, per_page=per_page)
    return success_response({"signs": signs, "total": total, "page": page, "per_page": per_page})


@teacher_bp.route("/signs/pending", methods=["GET"])
@jwt_required()
def pending_signs():
    """GET /api/signs/pending — All signs awaiting peer review."""
    return success_response(get_pending_signs())


@teacher_bp.route("/signs/approved", methods=["GET"])
@jwt_required()
def approved_signs():
    """GET /api/signs/approved — All approved signs visible to students."""
    return success_response(get_approved_signs())


@teacher_bp.route("/signs/<int:sign_id>", methods=["GET"])
@jwt_required()
def get_sign_detail(sign_id):
    """GET /api/signs/<id> — Single sign detail."""
    sign = get_sign(sign_id)
    if not sign:
        return error_response(f"Sign #{sign_id} not found.", 404)
    return success_response(sign)


@teacher_bp.route("/signs/stats", methods=["GET"])
@jwt_required()
def vocab_stats():
    """GET /api/signs/stats — Vocabulary aggregate stats."""
    return success_response(get_vocabulary_stats())


@teacher_bp.route("/signs/classes", methods=["GET"])
@jwt_required()
def get_classes():
    """GET /api/signs/classes — Load class labels from existing Janith model."""
    classes = load_classes()
    return success_response({"classes": classes, "count": len(classes)})


# ── Teacher list (admin use) ─────────────────────────────────────────────────

@teacher_bp.route("/teachers", methods=["GET"])
@jwt_required()
def list_teachers():
    """GET /api/teachers — List all teacher accounts."""
    teachers = list_users(role="teacher")
    return success_response(teachers)

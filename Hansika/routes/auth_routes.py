"""
routes/auth_routes.py
======================
Authentication endpoints — register, login, profile.

Research Component: SLSL Recognition System — Objective 4
Author: Hansika
"""

import logging
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from services.auth_service import register_user, login_user, get_user_by_id
from utils.response import success_response, error_response
from utils.validators import validate_register_payload, validate_login_payload

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/register", methods=["POST"])
def register():
    """
    POST /api/auth/register
    Register a new teacher account.

    Body: { username, email, password, full_name?, role? }
    """
    data = request.get_json(silent=True)
    err = validate_register_payload(data)
    if err:
        return error_response(err, 400)

    success, message, user = register_user(
        username=data["username"],
        email=data["email"],
        password=data["password"],
        full_name=data.get("full_name", ""),
        role=data.get("role", "teacher"),
    )
    if not success:
        return error_response(message, 409)
    return success_response(user, message, 201)


@auth_bp.route("/login", methods=["POST"])
def login():
    """
    POST /api/auth/login
    Authenticate and receive a JWT access token.

    Body: { username, password }
    Returns: { token, user }
    """
    data = request.get_json(silent=True)
    err = validate_login_payload(data)
    if err:
        return error_response(err, 400)

    success, token_or_msg, user = login_user(data["username"], data["password"])
    if not success:
        return error_response(token_or_msg, 401)

    return success_response({"token": token_or_msg, "user": user}, "Login successful.")


@auth_bp.route("/profile", methods=["GET"])
@jwt_required()
def profile():
    """
    GET /api/auth/profile
    Return the authenticated teacher's profile.
    Requires: Bearer token
    """
    user_id = get_jwt_identity()
    user = get_user_by_id(user_id)
    if not user:
        return error_response("User not found.", 404)
    return success_response(user)


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    """
    GET /api/auth/me
    Lightweight check — returns identity from JWT claims.
    """
    claims = get_jwt()
    return success_response({
        "id": get_jwt_identity(),
        "username": claims.get("username"),
        "role": claims.get("role"),
    })

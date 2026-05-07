"""
teacher_server.py
==================
Main entry point for the Hansika Teacher Dashboard Flask server.

Research Component: SLSL Recognition System — Objective 4
Author: Hansika

Run with:
    python teacher_server.py

Server starts on port 5001 (Janith server uses 5000).
"""

import logging
from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager

from config.settings import get_config
from database.db import init_db
from utils.logger import setup_logger

# ── Configure logger before importing routes ─────────────────────────────────
setup_logger("hansika")
logger = logging.getLogger("hansika")

# ── Load config ───────────────────────────────────────────────────────────────
cfg = get_config()
cfg.ensure_storage_dirs()


def create_app() -> Flask:
    """
    Application factory.
    Creates, configures, and returns the Flask app instance.
    """
    app = Flask(__name__, static_folder="static", template_folder="templates")

    # ── Core config ───────────────────────────────────────────────────────────
    app.config["SECRET_KEY"]                     = cfg.SECRET_KEY
    app.config["JWT_SECRET_KEY"]                 = cfg.JWT_SECRET_KEY
    app.config["JWT_ACCESS_TOKEN_EXPIRES"]       = cfg.JWT_ACCESS_TOKEN_EXPIRES
    app.config["MAX_CONTENT_LENGTH"]             = cfg.MAX_CONTENT_LENGTH

    # ── Extensions ────────────────────────────────────────────────────────────
    CORS(app, origins=cfg.CORS_ORIGINS, supports_credentials=True)
    JWTManager(app)

    # ── Register blueprints ───────────────────────────────────────────────────
    from routes.auth_routes       import auth_bp
    from routes.teacher_routes    import teacher_bp
    from routes.review_routes     import review_bp
    from routes.annotation_routes import annotation_bp
    from routes.assignment_routes import assignment_bp
    from routes.analytics_routes  import analytics_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(teacher_bp)
    app.register_blueprint(review_bp)
    app.register_blueprint(annotation_bp)
    app.register_blueprint(assignment_bp)
    app.register_blueprint(analytics_bp)

    # ── Health check ──────────────────────────────────────────────────────────
    @app.route("/api/health", methods=["GET"])
    def health():
        """GET /api/health — Simple liveness probe."""
        return jsonify({
            "status": "healthy",
            "service": "Hansika Teacher Dashboard",
            "component": "SLSL Recognition System — Objective 4",
            "port": cfg.PORT,
        }), 200

    # ── Global error handlers ─────────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"success": False, "message": "Endpoint not found."}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"success": False, "message": "Method not allowed."}), 405

    @app.errorhandler(413)
    def request_too_large(e):
        return jsonify({"success": False, "message": "File too large. Max 100 MB."}), 413

    @app.errorhandler(500)
    def internal_error(e):
        logger.exception("Internal server error: %s", e)
        return jsonify({"success": False, "message": "Internal server error."}), 500

    logger.info("Flask app created. Blueprints registered.")
    return app


def main():
    """Initialise database and start the development server."""
    logger.info("=" * 60)
    logger.info("Hansika Teacher Dashboard — SLSL Objective 4")
    logger.info("=" * 60)

    # Initialise SQLite schema
    logger.info("Initialising database at: %s", cfg.DATABASE_PATH)
    init_db()
    logger.info("Database ready.")

    # Start background retraining checker (checks every hour)
    from ml_integration.retrain_trigger import start_background_checker
    start_background_checker(interval_seconds=3600)
    logger.info("Background retraining checker started.")

    app = create_app()

    logger.info("Starting server on %s:%d", cfg.HOST, cfg.PORT)
    logger.info("Janith ML backend expected at: %s", cfg.JANITH_SERVER_URL)

    app.run(
        host=cfg.HOST,
        port=cfg.PORT,
        debug=cfg.DEBUG,
        use_reloader=False,   # Disable reloader to avoid double-starting threads
    )


if __name__ == "__main__":
    main()

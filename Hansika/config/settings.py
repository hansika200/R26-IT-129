"""
config/settings.py
==================
Centralized configuration for the Hansika Teacher Dashboard backend.
Loads from .env file; falls back to safe defaults for development.

Research Component: SLSL Recognition System — Objective 4
Author: Hansika
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the Hansika/ root
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Config:
    """Base configuration — shared across all environments."""

    # ── Flask Core ──────────────────────────────────────────────────────────
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-CHANGE-IN-PRODUCTION")
    FLASK_ENV: str = os.getenv("FLASK_ENV", "development")
    DEBUG: bool = os.getenv("FLASK_DEBUG", "1") == "1"
    HOST: str = os.getenv("FLASK_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("FLASK_PORT", 5001))

    # ── JWT ─────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "jwt-secret-CHANGE-IN-PRODUCTION")
    JWT_ACCESS_TOKEN_EXPIRES: int = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES", 86400))  # 24h

    # ── Database ─────────────────────────────────────────────────────────────
    MONGODB_URI: str = os.getenv(
        "MONGODB_URI",
        "mongodb://localhost:27017/?retryWrites=true&w=majority"
    )
    MONGODB_DB_NAME: str = os.getenv("MONGODB_DB_NAME", "hansika_db")

    # ── ML Integration (Janith pipeline) ────────────────────────────────────
    JANITH_MODELS_DIR: str = os.getenv(
        "JANITH_MODELS_DIR",
        str(BASE_DIR.parent / "Janith" / "models")
    )
    JANITH_TRAINING_DIR: str = os.getenv(
        "JANITH_TRAINING_DIR",
        str(BASE_DIR.parent / "Janith" / "training")
    )
    JANITH_MODEL_PATH: str = os.getenv(
        "JANITH_MODEL_PATH",
        str(BASE_DIR.parent / "Janith" / "models" / "slsl_model.tflite")
    )
    JANITH_CLASSES_PATH: str = os.getenv(
        "JANITH_CLASSES_PATH",
        str(BASE_DIR.parent / "Janith" / "models" / "classes.npy")
    )
    JANITH_SERVER_URL: str = os.getenv("JANITH_SERVER_URL", "http://127.0.0.1:5000")

    # ── Storage Directories ──────────────────────────────────────────────────
    TEACHER_RECORDINGS_DIR: str = os.getenv(
        "TEACHER_RECORDINGS_DIR",
        str(BASE_DIR / "storage" / "teacher_recordings")
    )
    STUDENT_RECORDINGS_DIR: str = os.getenv(
        "STUDENT_RECORDINGS_DIR",
        str(BASE_DIR / "storage" / "student_recordings")
    )
    APPROVED_SIGNS_DIR: str = os.getenv(
        "APPROVED_SIGNS_DIR",
        str(BASE_DIR / "storage" / "approved_signs")
    )
    REJECTED_SIGNS_DIR: str = os.getenv(
        "REJECTED_SIGNS_DIR",
        str(BASE_DIR / "storage" / "rejected_signs")
    )
    ANNOTATIONS_DIR: str = os.getenv(
        "ANNOTATIONS_DIR",
        str(BASE_DIR / "storage" / "annotations")
    )
    UPLOADS_DIR: str = os.getenv(
        "UPLOADS_DIR",
        str(BASE_DIR / "uploads")
    )

    # ── Upload Constraints ───────────────────────────────────────────────────
    MAX_CONTENT_LENGTH: int = 100 * 1024 * 1024   # 100 MB max upload
    ALLOWED_VIDEO_EXTENSIONS = {"mp4", "avi", "mov", "webm", "mkv"}
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg"}

    # ── Retraining Thresholds ────────────────────────────────────────────────
    MIN_SAMPLES_FOR_RETRAIN: int = int(os.getenv("MIN_SAMPLES_FOR_RETRAIN", 30))
    MIN_NEW_SIGNS_FOR_RETRAIN: int = int(os.getenv("MIN_NEW_SIGNS_FOR_RETRAIN", 5))

    # ── CORS ─────────────────────────────────────────────────────────────────
    CORS_ORIGINS: list = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:8080,http://localhost:5000"
    ).split(",")

    @classmethod
    def ensure_storage_dirs(cls) -> None:
        """Create all required storage directories if they don't exist."""
        dirs = [
            cls.TEACHER_RECORDINGS_DIR,
            cls.STUDENT_RECORDINGS_DIR,
            cls.APPROVED_SIGNS_DIR,
            cls.REJECTED_SIGNS_DIR,
            cls.ANNOTATIONS_DIR,
            cls.UPLOADS_DIR,
        ]
        for d in dirs:
            Path(d).mkdir(parents=True, exist_ok=True)


class DevelopmentConfig(Config):
    """Development-specific overrides."""
    DEBUG = True


class ProductionConfig(Config):
    """Production-specific overrides."""
    DEBUG = False


# Factory map
config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}

def get_config() -> Config:
    """Return the active config based on FLASK_ENV."""
    env = os.getenv("FLASK_ENV", "development")
    return config_map.get(env, DevelopmentConfig)

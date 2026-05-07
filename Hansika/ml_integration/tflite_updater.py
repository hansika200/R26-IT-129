"""
ml_integration/tflite_updater.py
====================================
TFLite model management utilities.

Handles copying updated .tflite models from the Janith output
directory to the correct active model path after retraining.

Research Component: SLSL Recognition System — Objective 4
Author: Hansika
"""

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from config.settings import get_config
from utils.helpers import sha256_file

logger = logging.getLogger(__name__)
cfg = get_config()


def get_active_model_info() -> dict:
    """
    Return metadata about the currently active TFLite model.

    Returns:
        {exists, path, size_bytes, sha256, last_modified}
    """
    model_path = Path(cfg.JANITH_MODEL_PATH)
    if not model_path.exists():
        return {"exists": False, "path": str(model_path)}
    stat = model_path.stat()
    return {
        "exists": True,
        "path": str(model_path),
        "size_bytes": stat.st_size,
        "sha256": sha256_file(str(model_path)),
        "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
    }


def backup_active_model() -> Tuple[bool, str]:
    """
    Create a timestamped backup of the current active model before replacing it.

    Returns:
        (success, backup_path_or_error)
    """
    model_path = Path(cfg.JANITH_MODEL_PATH)
    if not model_path.exists():
        return False, "Active model file not found — nothing to back up."

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_name = f"slsl_model_backup_{ts}.tflite"
    backup_path = model_path.parent / backup_name

    try:
        shutil.copy2(str(model_path), str(backup_path))
        logger.info("Model backed up → %s", backup_path)
        return True, str(backup_path)
    except Exception as exc:
        logger.exception("backup_active_model failed: %s", exc)
        return False, str(exc)


def promote_new_model(new_model_path: str) -> Tuple[bool, str]:
    """
    Replace the active model with a newly trained one.

    Steps:
    1. Validate the new file exists.
    2. Back up the current active model.
    3. Copy the new model to the active path.

    Args:
        new_model_path: Absolute path to the newly trained .tflite file.

    Returns:
        (success, message)
    """
    new_path = Path(new_model_path)
    if not new_path.exists():
        return False, f"New model file not found: {new_model_path}"

    ok, backup_info = backup_active_model()
    if not ok:
        logger.warning("Could not back up active model: %s. Proceeding anyway.", backup_info)

    active_path = Path(cfg.JANITH_MODEL_PATH)
    active_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        shutil.copy2(str(new_path), str(active_path))
        logger.info("New model promoted: %s → %s", new_path, active_path)
        return True, f"Model updated. Backup: {backup_info}"
    except Exception as exc:
        logger.exception("promote_new_model failed: %s", exc)
        return False, str(exc)


def list_model_backups() -> list:
    """Return a list of backup model files in the Janith models directory."""
    models_dir = Path(cfg.JANITH_MODELS_DIR)
    if not models_dir.exists():
        return []
    backups = sorted(
        [
            {
                "filename": f.name,
                "size_bytes": f.stat().st_size,
                "created": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            }
            for f in models_dir.glob("slsl_model_backup_*.tflite")
        ],
        key=lambda x: x["created"],
        reverse=True,
    )
    return backups

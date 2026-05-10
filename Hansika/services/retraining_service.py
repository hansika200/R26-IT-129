"""
services/retraining_service.py
================================
Retraining orchestration service.
Now using MongoDB via RetrainingRepository.

Research Component: SLSL Recognition System — Objective 4
"""

import logging
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime

from config.settings import get_config
from repositories.retraining_repository import RetrainingRepository
from database.collections import get_signs_collection, get_annotations_collection

logger = logging.getLogger(__name__)
cfg = get_config()


def check_retrain_eligibility() -> dict:
    try:
        signs_coll = get_signs_collection()
        ann_coll = get_annotations_collection()

        new_signs = signs_coll.count_documents({"status": "approved", "is_in_model": 0})
        new_samples = ann_coll.count_documents({"is_correct": 1, "included_in_dataset": 0})

        reasons = []
        if new_signs >= cfg.MIN_NEW_SIGNS_FOR_RETRAIN:
            reasons.append(f"{new_signs} new approved signs (threshold: {cfg.MIN_NEW_SIGNS_FOR_RETRAIN})")
        if new_samples >= cfg.MIN_SAMPLES_FOR_RETRAIN:
            reasons.append(f"{new_samples} new labelled samples (threshold: {cfg.MIN_SAMPLES_FOR_RETRAIN})")

        return {
            "should_retrain": bool(reasons),
            "reason": "; ".join(reasons) if reasons else "Thresholds not met",
            "new_signs_count": new_signs,
            "new_samples_count": new_samples,
        }
    except Exception as exc:
        logger.exception("check_retrain_eligibility failed: %s", exc)
        return {"should_retrain": False, "reason": str(exc)}


def _create_log_entry(reason: str, triggered_by: Optional[str], new_signs: list, sample_count: int) -> str:
    payload = {
        "triggered_by": triggered_by,
        "trigger_reason": reason,
        "new_signs": new_signs,
        "sample_count": sample_count,
        "status": "pending",
        "model_path": "",
        "error_message": "",
        "started_at": datetime.utcnow().isoformat(),
        "completed_at": None,
    }
    log = RetrainingRepository.create_log(payload)
    return log["_id"]


def trigger_retraining(
    triggered_by: Optional[str] = None,
    reason: str = "manual",
) -> Tuple[bool, str, Optional[dict]]:
    train_script = Path(cfg.JANITH_TRAINING_DIR) / "train_model.py"
    if not train_script.exists():
        msg = f"train_model.py not found at {train_script}. Cannot retrain."
        logger.error(msg)
        return False, msg, None

    try:
        new_sign_docs = RetrainingRepository.get_new_approved_signs()
        new_signs = [d["label"] for d in new_sign_docs]
        new_sign_ids = [d["_id"] for d in new_sign_docs]

        ann_coll = get_annotations_collection()
        new_ann_ids = [str(d["_id"]) for d in ann_coll.find({"is_correct": 1, "included_in_dataset": 0}, {"_id": 1})]

        log_id = _create_log_entry(
            reason=reason,
            triggered_by=triggered_by,
            new_signs=new_signs,
            sample_count=len(new_ann_ids),
        )

        logger.info("Retraining log#%s started. Signs: %s", log_id, new_signs)
        RetrainingRepository.update_log(log_id, "running")

        result = subprocess.run(
            [sys.executable, str(train_script)],
            capture_output=True,
            text=True,
            timeout=1800,
            cwd=str(Path(cfg.JANITH_TRAINING_DIR).parent),
        )

        if result.returncode != 0:
            err = result.stderr[:2000]
            logger.error("train_model.py exited with code %d: %s", result.returncode, err)
            RetrainingRepository.update_log(log_id, "failed", error=err)
            return False, f"Retraining failed (exit {result.returncode}).", None

        model_path = cfg.JANITH_MODEL_PATH
        RetrainingRepository.update_log(log_id, "success", model_path=model_path)

        if new_sign_ids:
            RetrainingRepository.mark_signs_in_model(new_sign_ids, datetime.utcnow().isoformat())

        if new_ann_ids:
            from repositories.annotation_repository import AnnotationRepository
            for aid in new_ann_ids:
                AnnotationRepository.mark_included(aid)

        log = RetrainingRepository.get_log(log_id)
        logger.info("Retraining log#%s completed successfully.", log_id)
        return True, "Retraining completed successfully.", log

    except subprocess.TimeoutExpired:
        RetrainingRepository.update_log(log_id, "failed", error="Timed out after 30 minutes.")
        return False, "Retraining timed out.", None
    except Exception as exc:
        # If log_id exists, try to update it
        try:
            RetrainingRepository.update_log(log_id, "failed", error=str(exc))
        except:
            pass
        logger.exception("trigger_retraining failed: %s", exc)
        return False, f"Retraining error: {exc}", None


def list_retraining_logs(page: int = 1, per_page: int = 20) -> Tuple[list, int]:
    try:
        return RetrainingRepository.list_logs(page, per_page)
    except Exception as exc:
        logger.exception("list_retraining_logs failed: %s", exc)
        return [], 0

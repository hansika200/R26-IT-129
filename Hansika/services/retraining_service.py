"""
services/retraining_service.py
================================
Retraining orchestration service.

Detects when enough approved signs or annotated data exist to
warrant a new training run, then triggers the existing Janith
train_model.py pipeline via subprocess.

Research Component: SLSL Recognition System — Objective 4
Author: Hansika
"""

import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from database.db import db_context, row_to_dict, rows_to_list
from database.models import RetrainingLogModel
from config.settings import get_config
from utils.helpers import utcnow_iso

logger = logging.getLogger(__name__)
cfg = get_config()


def check_retrain_eligibility() -> dict:
    """
    Check whether the current data warrants triggering a retraining run.

    Criteria:
    1. ≥ MIN_NEW_SIGNS_FOR_RETRAIN approved signs not yet in the model.
    2. ≥ MIN_SAMPLES_FOR_RETRAIN correct annotations not yet exported.

    Returns:
        {
          "should_retrain": bool,
          "reason": str,
          "new_signs_count": int,
          "new_samples_count": int
        }
    """
    try:
        with db_context() as conn:
            new_signs = conn.execute(
                "SELECT COUNT(*) FROM signs WHERE status='approved' AND is_in_model=0"
            ).fetchone()[0]
            new_samples = conn.execute(
                "SELECT COUNT(*) FROM annotations WHERE is_correct=1 AND included_in_dataset=0"
            ).fetchone()[0]

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


def _create_log_entry(reason: str, triggered_by: Optional[int], new_signs: list, sample_count: int) -> int:
    """Insert a retraining log entry and return its ID."""
    payload = RetrainingLogModel.create_payload(
        trigger_reason=reason,
        triggered_by=triggered_by,
        new_signs=new_signs,
        sample_count=sample_count,
    )
    with db_context() as conn:
        cursor = conn.execute(
            """INSERT INTO retraining_logs
               (triggered_by, trigger_reason, new_signs, sample_count,
                status, model_path, error_message, started_at)
               VALUES
               (:triggered_by, :trigger_reason, :new_signs, :sample_count,
                :status, :model_path, :error_message, :started_at)""",
            payload,
        )
        return cursor.lastrowid


def _update_log(log_id: int, status: str, model_path: str = "", error: str = "") -> None:
    """Update an existing retraining log entry."""
    with db_context() as conn:
        conn.execute(
            """UPDATE retraining_logs
               SET status=?, model_path=?, error_message=?, finished_at=?
               WHERE id=?""",
            (status, model_path, error, utcnow_iso(), log_id),
        )


def trigger_retraining(
    triggered_by: Optional[int] = None,
    reason: str = RetrainingLogModel.REASON_MANUAL,
) -> Tuple[bool, str, Optional[dict]]:
    """
    Launch the existing Janith train_model.py as a subprocess.

    Steps:
    1. Log the start of retraining.
    2. Call Janith/training/train_model.py via subprocess.
    3. Update log with success/failure.
    4. Mark newly approved signs as is_in_model=1.
    5. Mark exported annotations as included_in_dataset=1.

    Returns:
        (success, message, log_dict)
    """
    train_script = Path(cfg.JANITH_TRAINING_DIR) / "train_model.py"
    if not train_script.exists():
        msg = f"train_model.py not found at {train_script}. Cannot retrain."
        logger.error(msg)
        return False, msg, None

    # Collect what we are training on
    with db_context() as conn:
        new_sign_rows = conn.execute(
            "SELECT id, label FROM signs WHERE status='approved' AND is_in_model=0"
        ).fetchall()
        new_ann_ids = [
            r[0] for r in conn.execute(
                "SELECT id FROM annotations WHERE is_correct=1 AND included_in_dataset=0"
            ).fetchall()
        ]

    new_signs  = [dict(r)["label"] for r in new_sign_rows]
    new_sign_ids = [dict(r)["id"] for r in new_sign_rows]

    log_id = _create_log_entry(
        reason=reason,
        triggered_by=triggered_by,
        new_signs=new_signs,
        sample_count=len(new_ann_ids),
    )

    logger.info("Retraining log#%d started. Signs: %s", log_id, new_signs)

    try:
        # Mark log as running
        _update_log(log_id, RetrainingLogModel.STATUS_RUNNING)

        result = subprocess.run(
            [sys.executable, str(train_script)],
            capture_output=True,
            text=True,
            timeout=1800,  # 30-minute timeout
            cwd=str(Path(cfg.JANITH_TRAINING_DIR).parent),
        )

        if result.returncode != 0:
            err = result.stderr[:2000]
            logger.error("train_model.py exited with code %d: %s", result.returncode, err)
            _update_log(log_id, RetrainingLogModel.STATUS_FAILED, error=err)
            return False, f"Retraining failed (exit {result.returncode}).", None

        # Success — update records
        model_path = cfg.JANITH_MODEL_PATH
        _update_log(log_id, RetrainingLogModel.STATUS_SUCCESS, model_path=model_path)

        # Mark signs as in-model
        if new_sign_ids:
            placeholders = ",".join("?" for _ in new_sign_ids)
            with db_context() as conn:
                conn.execute(
                    f"UPDATE signs SET is_in_model=1, updated_at=? WHERE id IN ({placeholders})",
                    [utcnow_iso()] + new_sign_ids,
                )

        # Mark annotations as exported
        if new_ann_ids:
            placeholders = ",".join("?" for _ in new_ann_ids)
            with db_context() as conn:
                conn.execute(
                    f"UPDATE annotations SET included_in_dataset=1 WHERE id IN ({placeholders})",
                    new_ann_ids,
                )

        log = _get_log(log_id)
        logger.info("Retraining log#%d completed successfully.", log_id)
        return True, "Retraining completed successfully.", log

    except subprocess.TimeoutExpired:
        _update_log(log_id, RetrainingLogModel.STATUS_FAILED, error="Timed out after 30 minutes.")
        return False, "Retraining timed out.", None
    except Exception as exc:
        _update_log(log_id, RetrainingLogModel.STATUS_FAILED, error=str(exc))
        logger.exception("trigger_retraining failed: %s", exc)
        return False, f"Retraining error: {exc}", None


def _get_log(log_id: int) -> Optional[dict]:
    try:
        with db_context() as conn:
            row = conn.execute(
                "SELECT * FROM retraining_logs WHERE id=?", (log_id,)
            ).fetchone()
        return row_to_dict(row) if row else None
    except Exception:
        return None


def list_retraining_logs(page: int = 1, per_page: int = 20) -> Tuple[list, int]:
    """Return paginated retraining log history."""
    try:
        offset = (page - 1) * per_page
        with db_context() as conn:
            total = conn.execute("SELECT COUNT(*) FROM retraining_logs").fetchone()[0]
            rows  = conn.execute(
                "SELECT * FROM retraining_logs ORDER BY started_at DESC LIMIT ? OFFSET ?",
                (per_page, offset),
            ).fetchall()
        result = []
        for r in rows_to_list(rows):
            r["new_signs"] = json.loads(r.get("new_signs") or "[]")
            result.append(r)
        return result, total
    except Exception as exc:
        logger.exception("list_retraining_logs failed: %s", exc)
        return [], 0

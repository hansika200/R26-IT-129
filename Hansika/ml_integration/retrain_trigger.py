"""
ml_integration/retrain_trigger.py
====================================
Automated retraining trigger checker.

Can be run as a background thread or called from the retraining API endpoint.
Checks eligibility and fires retraining when thresholds are met.

Research Component: SLSL Recognition System — Objective 4
Author: Hansika
"""

import logging
import threading
import time

from services.retraining_service import check_retrain_eligibility, trigger_retraining
from database.models import RetrainingLogModel

logger = logging.getLogger(__name__)

_trigger_lock = threading.Lock()


def auto_check_and_trigger() -> dict:
    """
    Check retraining eligibility and trigger if thresholds are met.
    Thread-safe — uses a lock to prevent concurrent retraining runs.

    Returns:
        {triggered: bool, reason: str, log: dict | None}
    """
    eligibility = check_retrain_eligibility()

    if not eligibility.get("should_retrain"):
        logger.info("Auto-retrain check: %s", eligibility.get("reason"))
        return {"triggered": False, "reason": eligibility.get("reason"), "log": None}

    if not _trigger_lock.acquire(blocking=False):
        return {"triggered": False, "reason": "Another retraining run is already in progress.", "log": None}

    try:
        logger.info("Auto-retrain triggered: %s", eligibility.get("reason"))
        success, message, log = trigger_retraining(
            triggered_by=None,
            reason=RetrainingLogModel.REASON_AUTO,
        )
        return {"triggered": success, "reason": message, "log": log}
    finally:
        _trigger_lock.release()


def start_background_checker(interval_seconds: int = 3600) -> threading.Thread:
    """
    Start a background daemon thread that periodically checks for retraining.

    Args:
        interval_seconds: How often to check (default 1 hour).

    Returns:
        The running Thread object.
    """
    def _worker():
        logger.info("Background retrain checker started (interval=%ds).", interval_seconds)
        while True:
            try:
                result = auto_check_and_trigger()
                if result["triggered"]:
                    logger.info("Background retrain: %s", result["reason"])
            except Exception as exc:
                logger.exception("Background retrain checker error: %s", exc)
            time.sleep(interval_seconds)

    thread = threading.Thread(target=_worker, daemon=True, name="retrain-checker")
    thread.start()
    return thread

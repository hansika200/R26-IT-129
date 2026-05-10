"""
services/analytics_service.py
================================
Analytics service for teacher dashboard.
Now using MongoDB via AnalyticsRepository.

Research Component: SLSL Recognition System — Objective 4
"""

import logging
from typing import Optional

from repositories.analytics_repository import AnalyticsRepository

logger = logging.getLogger(__name__)


def get_dashboard_summary() -> dict:
    try:
        return AnalyticsRepository.get_dashboard_summary()
    except Exception as exc:
        logger.exception("get_dashboard_summary failed: %s", exc)
        return {}


def get_student_performance_overview(assignment_id: Optional[str] = None) -> list:
    try:
        return AnalyticsRepository.get_student_performance_overview(assignment_id)
    except Exception as exc:
        logger.exception("get_student_performance_overview failed: %s", exc)
        return []


def get_struggling_students(score_threshold: float = 50.0) -> list:
    try:
        return AnalyticsRepository.get_struggling_students(score_threshold)
    except Exception as exc:
        logger.exception("get_struggling_students failed: %s", exc)
        return []


def get_sign_difficulty_report() -> list:
    try:
        return AnalyticsRepository.get_sign_difficulty_report()
    except Exception as exc:
        logger.exception("get_sign_difficulty_report failed: %s", exc)
        return []


def get_activity_trend(days: int = 30) -> list:
    try:
        return AnalyticsRepository.get_activity_trend(days)
    except Exception as exc:
        logger.exception("get_activity_trend failed: %s", exc)
        return []


def get_assignment_completion_report() -> list:
    try:
        return AnalyticsRepository.get_assignment_completion_report()
    except Exception as exc:
        logger.exception("get_assignment_completion_report failed: %s", exc)
        return []

"""
services/analytics_service.py
================================
Analytics service for teacher dashboard.
Research Component: SLSL Recognition System — Objective 4
Author: Hansika
"""

import logging
from typing import Optional

from database.db import db_context, rows_to_list

logger = logging.getLogger(__name__)


def get_dashboard_summary() -> dict:
    """High-level summary card for the teacher dashboard."""
    try:
        with db_context() as conn:
            total_signs    = conn.execute("SELECT COUNT(*) FROM signs").fetchone()[0]
            pending_signs  = conn.execute("SELECT COUNT(*) FROM signs WHERE status='pending'").fetchone()[0]
            approved_signs = conn.execute("SELECT COUNT(*) FROM signs WHERE status='approved'").fetchone()[0]
            pending_annots = conn.execute("SELECT COUNT(*) FROM student_recordings WHERE is_annotated=0").fetchone()[0]
            active_assigns = conn.execute("SELECT COUNT(*) FROM assignments WHERE is_active=1").fetchone()[0]
            unique_students= conn.execute("SELECT COUNT(DISTINCT student_id) FROM student_progress").fetchone()[0]
            retrain_ok     = conn.execute("SELECT COUNT(*) FROM retraining_logs WHERE status='success'").fetchone()[0]
        return {
            "vocabulary": {"total": total_signs, "pending": pending_signs, "approved": approved_signs},
            "pending_annotations": pending_annots,
            "active_assignments": active_assigns,
            "unique_students": unique_students,
            "successful_retraining_runs": retrain_ok,
        }
    except Exception as exc:
        logger.exception("get_dashboard_summary failed: %s", exc)
        return {}


def get_student_performance_overview(assignment_id: Optional[int] = None) -> list:
    """Per-student avg score/completion, optionally filtered by assignment."""
    try:
        clause = "WHERE sp.assignment_id = ?" if assignment_id else ""
        params = [assignment_id] if assignment_id else []
        with db_context() as conn:
            rows = conn.execute(
                f"""SELECT sp.student_id,
                       ROUND(AVG(sp.score),1) AS avg_score,
                       ROUND(AVG(sp.completion_pct),1) AS avg_completion,
                       COUNT(DISTINCT sp.assignment_id) AS assignment_count,
                       MAX(sp.last_activity) AS last_activity
                    FROM student_progress sp {clause}
                    GROUP BY sp.student_id ORDER BY avg_score DESC""", params
            ).fetchall()
        return rows_to_list(rows)
    except Exception as exc:
        logger.exception("get_student_performance_overview failed: %s", exc)
        return []


def get_struggling_students(score_threshold: float = 50.0) -> list:
    """Students with average score below threshold."""
    try:
        with db_context() as conn:
            rows = conn.execute(
                """SELECT student_id, ROUND(AVG(score),1) AS avg_score, COUNT(*) AS assignment_count
                   FROM student_progress GROUP BY student_id
                   HAVING avg_score < ? ORDER BY avg_score ASC""", (score_threshold,)
            ).fetchall()
        return rows_to_list(rows)
    except Exception as exc:
        logger.exception("get_struggling_students failed: %s", exc)
        return []


def get_sign_difficulty_report() -> list:
    """Signs with the highest error rates based on annotations."""
    try:
        with db_context() as conn:
            rows = conn.execute(
                """SELECT sr.sign_label,
                       COUNT(*) AS total_attempts,
                       SUM(CASE WHEN a.is_correct=0 THEN 1 ELSE 0 END) AS error_count,
                       ROUND(SUM(CASE WHEN a.is_correct=0 THEN 1 ELSE 0 END)*100.0/COUNT(*),1) AS error_rate_pct
                   FROM annotations a
                   JOIN student_recordings sr ON a.recording_id=sr.id
                   GROUP BY sr.sign_label ORDER BY error_count DESC"""
            ).fetchall()
        return rows_to_list(rows)
    except Exception as exc:
        logger.exception("get_sign_difficulty_report failed: %s", exc)
        return []


def get_activity_trend(days: int = 30) -> list:
    """Daily recording counts over the last N days."""
    try:
        with db_context() as conn:
            rows = conn.execute(
                """SELECT DATE(created_at) AS date, COUNT(*) AS recording_count
                   FROM student_recordings
                   WHERE created_at >= DATE('now', ? || ' days')
                   GROUP BY DATE(created_at) ORDER BY date ASC""", (f"-{days}",)
            ).fetchall()
        return rows_to_list(rows)
    except Exception as exc:
        logger.exception("get_activity_trend failed: %s", exc)
        return []


def get_assignment_completion_report() -> list:
    """Per-assignment completion and score overview."""
    try:
        with db_context() as conn:
            rows = conn.execute(
                """SELECT a.id AS assignment_id, a.title,
                       COUNT(sp.student_id) AS student_count,
                       ROUND(AVG(sp.score),1) AS avg_score,
                       ROUND(AVG(sp.completion_pct),1) AS avg_completion
                   FROM assignments a
                   LEFT JOIN student_progress sp ON a.id=sp.assignment_id
                   WHERE a.is_active=1 GROUP BY a.id ORDER BY avg_score DESC"""
            ).fetchall()
        return rows_to_list(rows)
    except Exception as exc:
        logger.exception("get_assignment_completion_report failed: %s", exc)
        return []

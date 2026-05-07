"""
services/assignment_service.py
================================
Assignment management service.

Teachers create sign-language practice assignments for students.
Progress is tracked per (student_id, assignment_id).

Research Component: SLSL Recognition System — Objective 4
Author: Hansika
"""

import json
import logging
from typing import Optional, Tuple

from database.db import db_context, row_to_dict, rows_to_list
from database.models import AssignmentModel, StudentProgressModel
from utils.helpers import utcnow_iso, safe_json_loads

logger = logging.getLogger(__name__)


# ── Assignment CRUD ───────────────────────────────────────────────────────────

def create_assignment(
    title: str,
    created_by: int,
    sign_labels: list,
    description: str = "",
    due_date: Optional[str] = None,
) -> Tuple[bool, str, Optional[dict]]:
    """
    Create a new assignment.

    Returns:
        (success, message, assignment_dict)
    """
    try:
        payload = AssignmentModel.create_payload(
            title=title,
            created_by=created_by,
            sign_labels=sign_labels,
            description=description,
            due_date=due_date,
        )
        with db_context() as conn:
            cursor = conn.execute(
                """INSERT INTO assignments
                   (title, description, created_by, sign_labels, due_date,
                    is_active, created_at, updated_at)
                   VALUES
                   (:title, :description, :created_by, :sign_labels, :due_date,
                    :is_active, :created_at, :updated_at)""",
                payload,
            )
            a = row_to_dict(
                conn.execute(
                    "SELECT * FROM assignments WHERE id = ?", (cursor.lastrowid,)
                ).fetchone()
            )
        a["sign_labels"] = safe_json_loads(a.get("sign_labels"), [])
        return True, "Assignment created.", a
    except Exception as exc:
        logger.exception("create_assignment failed: %s", exc)
        return False, f"Failed to create assignment: {exc}", None


def get_assignment(assignment_id: int) -> Optional[dict]:
    """Return a single assignment or None."""
    try:
        with db_context() as conn:
            row = conn.execute(
                "SELECT * FROM assignments WHERE id = ?", (assignment_id,)
            ).fetchone()
        if not row:
            return None
        a = row_to_dict(row)
        a["sign_labels"] = safe_json_loads(a.get("sign_labels"), [])
        return a
    except Exception as exc:
        logger.exception("get_assignment(%s) failed: %s", assignment_id, exc)
        return None


def list_assignments(
    created_by: Optional[int] = None,
    is_active: Optional[bool] = None,
    page: int = 1,
    per_page: int = 20,
) -> Tuple[list, int]:
    """Return assignments with optional filters."""
    try:
        clauses, params = [], []
        if created_by is not None:
            clauses.append("created_by = ?")
            params.append(created_by)
        if is_active is not None:
            clauses.append("is_active = ?")
            params.append(1 if is_active else 0)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        offset = (page - 1) * per_page

        with db_context() as conn:
            total = conn.execute(
                f"SELECT COUNT(*) FROM assignments {where}", params
            ).fetchone()[0]
            rows = conn.execute(
                f"SELECT * FROM assignments {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                params + [per_page, offset],
            ).fetchall()

        result = []
        for r in rows_to_list(rows):
            r["sign_labels"] = safe_json_loads(r.get("sign_labels"), [])
            result.append(r)
        return result, total
    except Exception as exc:
        logger.exception("list_assignments failed: %s", exc)
        return [], 0


def deactivate_assignment(assignment_id: int) -> bool:
    """Mark assignment as inactive (soft delete)."""
    try:
        with db_context() as conn:
            conn.execute(
                "UPDATE assignments SET is_active = 0, updated_at = ? WHERE id = ?",
                (utcnow_iso(), assignment_id),
            )
        return True
    except Exception as exc:
        logger.exception("deactivate_assignment failed: %s", exc)
        return False


# ── Student Progress ──────────────────────────────────────────────────────────

def upsert_student_progress(
    student_id: str,
    assignment_id: int,
    sign_label: str,
    is_correct: bool,
) -> Tuple[bool, str]:
    """
    Update a student's progress on an assignment after a practice attempt.

    Inserts a new progress row if none exists, otherwise updates it.

    Returns:
        (success, message)
    """
    try:
        with db_context() as conn:
            # Fetch assignment sign list
            assignment = conn.execute(
                "SELECT sign_labels FROM assignments WHERE id = ?", (assignment_id,)
            ).fetchone()
            if not assignment:
                return False, f"Assignment #{assignment_id} not found."

            total_signs = safe_json_loads(dict(assignment)["sign_labels"], [])

            # Fetch existing progress
            existing = conn.execute(
                "SELECT * FROM student_progress WHERE student_id = ? AND assignment_id = ?",
                (student_id, assignment_id),
            ).fetchone()

            if existing:
                row = dict(existing)
                attempted = safe_json_loads(row["signs_attempted"], [])
                correct   = safe_json_loads(row["signs_correct"], [])

                if sign_label not in attempted:
                    attempted.append(sign_label)
                if is_correct and sign_label not in correct:
                    correct.append(sign_label)

                completion = len(attempted) / len(total_signs) * 100 if total_signs else 0
                score      = len(correct)  / len(total_signs) * 100 if total_signs else 0

                conn.execute(
                    """UPDATE student_progress
                       SET signs_attempted = ?, signs_correct = ?,
                           score = ?, completion_pct = ?, last_activity = ?
                       WHERE student_id = ? AND assignment_id = ?""",
                    (json.dumps(attempted), json.dumps(correct),
                     round(score, 1), round(completion, 1), utcnow_iso(),
                     student_id, assignment_id),
                )
            else:
                attempted = [sign_label]
                correct   = [sign_label] if is_correct else []
                completion = len(attempted) / len(total_signs) * 100 if total_signs else 0
                score      = len(correct)  / len(total_signs) * 100 if total_signs else 0
                payload = StudentProgressModel.create_payload(
                    student_id=student_id,
                    assignment_id=assignment_id,
                    signs_attempted=attempted,
                    signs_correct=correct,
                    score=round(score, 1),
                    completion_pct=round(completion, 1),
                )
                conn.execute(
                    """INSERT OR REPLACE INTO student_progress
                       (student_id, assignment_id, signs_attempted, signs_correct,
                        score, completion_pct, last_activity)
                       VALUES
                       (:student_id, :assignment_id, :signs_attempted, :signs_correct,
                        :score, :completion_pct, :last_activity)""",
                    payload,
                )

        return True, "Progress updated."
    except Exception as exc:
        logger.exception("upsert_student_progress failed: %s", exc)
        return False, f"Failed to update progress: {exc}"


def get_student_progress(student_id: str, assignment_id: int) -> Optional[dict]:
    """Return a student's progress on a specific assignment."""
    try:
        with db_context() as conn:
            row = conn.execute(
                "SELECT * FROM student_progress WHERE student_id = ? AND assignment_id = ?",
                (student_id, assignment_id),
            ).fetchone()
        if not row:
            return None
        p = row_to_dict(row)
        p["signs_attempted"] = safe_json_loads(p.get("signs_attempted"), [])
        p["signs_correct"]   = safe_json_loads(p.get("signs_correct"), [])
        return p
    except Exception as exc:
        logger.exception("get_student_progress failed: %s", exc)
        return None


def get_all_progress_for_assignment(assignment_id: int) -> list:
    """Return all students' progress for a given assignment."""
    try:
        with db_context() as conn:
            rows = conn.execute(
                "SELECT * FROM student_progress WHERE assignment_id = ? ORDER BY score DESC",
                (assignment_id,),
            ).fetchall()
        result = []
        for r in rows_to_list(rows):
            r["signs_attempted"] = safe_json_loads(r.get("signs_attempted"), [])
            r["signs_correct"]   = safe_json_loads(r.get("signs_correct"), [])
            result.append(r)
        return result
    except Exception as exc:
        logger.exception("get_all_progress_for_assignment failed: %s", exc)
        return []

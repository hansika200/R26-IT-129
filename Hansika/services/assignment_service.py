"""
services/assignment_service.py
================================
Assignment management service.
Now using MongoDB via AssignmentRepository.

Research Component: SLSL Recognition System — Objective 4
"""

import logging
from typing import Optional, Tuple
from datetime import datetime

from repositories.assignment_repository import AssignmentRepository, StudentProgressRepository
from database.collections import get_assignments_collection, get_student_progress_collection
from utils.bson_helper import object_id_to_str, str_to_object_id

logger = logging.getLogger(__name__)

# ── Assignment CRUD ───────────────────────────────────────────────────────────

def create_assignment(
    title: str,
    created_by: str,
    sign_labels: list,
    description: str = "",
    due_date: Optional[str] = None,
) -> Tuple[bool, str, Optional[dict]]:
    try:
        now = datetime.utcnow().isoformat()
        payload = {
            "title": title,
            "description": description,
            "created_by": created_by,
            "sign_labels": sign_labels,
            "due_date": due_date,
            "is_active": 1,
            "created_at": now,
            "updated_at": now,
        }
        a = AssignmentRepository.create_assignment(payload)
        return True, "Assignment created.", a
    except Exception as exc:
        logger.exception("create_assignment failed: %s", exc)
        return False, f"Failed to create assignment: {exc}", None


def get_assignment(assignment_id: str) -> Optional[dict]:
    try:
        coll = get_assignments_collection()
        doc = coll.find_one({"_id": str_to_object_id(assignment_id)})
        return object_id_to_str(doc)
    except Exception as exc:
        logger.exception("get_assignment(%s) failed: %s", assignment_id, exc)
        return None


def list_assignments(
    created_by: Optional[str] = None,
    is_active: Optional[bool] = None,
    page: int = 1,
    per_page: int = 20,
) -> Tuple[list, int]:
    try:
        coll = get_assignments_collection()
        query = {}
        if created_by:
            query["created_by"] = created_by
        if is_active is not None:
            query["is_active"] = 1 if is_active else 0
            
        total = coll.count_documents(query)
        cursor = coll.find(query).sort("created_at", -1).skip((page - 1) * per_page).limit(per_page)
        
        return [object_id_to_str(doc) for doc in cursor], total
    except Exception as exc:
        logger.exception("list_assignments failed: %s", exc)
        return [], 0


def deactivate_assignment(assignment_id: str) -> bool:
    try:
        coll = get_assignments_collection()
        res = coll.update_one(
            {"_id": str_to_object_id(assignment_id)},
            {"$set": {"is_active": 0, "updated_at": datetime.utcnow().isoformat()}}
        )
        return res.modified_count > 0
    except Exception as exc:
        logger.exception("deactivate_assignment failed: %s", exc)
        return False


# ── Student Progress ──────────────────────────────────────────────────────────

def upsert_student_progress(
    student_id: str,
    assignment_id: str,
    sign_label: str,
    is_correct: bool,
) -> Tuple[bool, str]:
    try:
        assign_coll = get_assignments_collection()
        assignment = assign_coll.find_one({"_id": str_to_object_id(assignment_id)})
        if not assignment:
            return False, f"Assignment #{assignment_id} not found."

        total_signs = assignment.get("sign_labels", [])
        prog_coll = get_student_progress_collection()
        existing = prog_coll.find_one({"student_id": student_id, "assignment_id": assignment_id})

        if existing:
            attempted = existing.get("signs_attempted", [])
            correct = existing.get("signs_correct", [])

            if sign_label not in attempted:
                attempted.append(sign_label)
            if is_correct and sign_label not in correct:
                correct.append(sign_label)

            completion = len(attempted) / len(total_signs) * 100 if total_signs else 0
            score = len(correct) / len(total_signs) * 100 if total_signs else 0

            prog_coll.update_one(
                {"_id": existing["_id"]},
                {"$set": {
                    "signs_attempted": attempted,
                    "signs_correct": correct,
                    "score": round(score, 1),
                    "completion_pct": round(completion, 1),
                    "last_activity": datetime.utcnow().isoformat()
                }}
            )
        else:
            attempted = [sign_label]
            correct = [sign_label] if is_correct else []
            completion = len(attempted) / len(total_signs) * 100 if total_signs else 0
            score = len(correct) / len(total_signs) * 100 if total_signs else 0
            
            payload = {
                "student_id": student_id,
                "assignment_id": assignment_id,
                "signs_attempted": attempted,
                "signs_correct": correct,
                "score": round(score, 1),
                "completion_pct": round(completion, 1),
                "last_activity": datetime.utcnow().isoformat()
            }
            StudentProgressRepository.create_progress(payload)

        return True, "Progress updated."
    except Exception as exc:
        logger.exception("upsert_student_progress failed: %s", exc)
        return False, f"Failed to update progress: {exc}"


def get_student_progress(student_id: str, assignment_id: str) -> Optional[dict]:
    try:
        prog_coll = get_student_progress_collection()
        doc = prog_coll.find_one({"student_id": student_id, "assignment_id": assignment_id})
        return object_id_to_str(doc)
    except Exception as exc:
        logger.exception("get_student_progress failed: %s", exc)
        return None


def get_all_progress_for_assignment(assignment_id: str) -> list:
    try:
        prog_coll = get_student_progress_collection()
        cursor = prog_coll.find({"assignment_id": assignment_id}).sort("score", -1)
        return [object_id_to_str(doc) for doc in cursor]
    except Exception as exc:
        logger.exception("get_all_progress_for_assignment failed: %s", exc)
        return []

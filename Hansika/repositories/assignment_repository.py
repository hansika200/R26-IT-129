"""
repositories/assignment_repository.py
=====================================
Repository for Assignments and Student Progress.

Research Component: SLSL Recognition System — Objective 4
"""

from database.collections import get_assignments_collection, get_student_progress_collection
from utils.bson_helper import object_id_to_str, str_to_object_id
from typing import Tuple

class AssignmentRepository:
    @staticmethod
    def create_assignment(payload: dict) -> dict:
        coll = get_assignments_collection()
        res = coll.insert_one(payload)
        payload['_id'] = res.inserted_id
        return object_id_to_str(payload)

    @staticmethod
    def list_assignments(page: int = 1, per_page: int = 20) -> Tuple[list, int]:
        coll = get_assignments_collection()
        total = coll.count_documents({})
        cursor = coll.find({}).sort("created_at", -1).skip((page - 1) * per_page).limit(per_page)
        return [object_id_to_str(doc) for doc in cursor], total

class StudentProgressRepository:
    @staticmethod
    def create_progress(payload: dict) -> dict:
        coll = get_student_progress_collection()
        res = coll.insert_one(payload)
        payload['_id'] = res.inserted_id
        return object_id_to_str(payload)

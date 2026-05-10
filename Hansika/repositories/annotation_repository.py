"""
repositories/annotation_repository.py
=====================================
Repository for Annotations and Student Recordings.

Research Component: SLSL Recognition System — Objective 4
"""

from typing import Tuple, Optional
from database.collections import get_annotations_collection
from utils.bson_helper import object_id_to_str, str_to_object_id

class AnnotationRepository:
    
    @staticmethod
    def create_annotation(payload: dict) -> dict:
        coll = get_annotations_collection()
        res = coll.insert_one(payload)
        payload['_id'] = res.inserted_id
        return object_id_to_str(payload)

    @staticmethod
    def list_annotations(
        student_id: Optional[str] = None,
        is_correct: Optional[bool] = None,
        page: int = 1,
        per_page: int = 20
    ) -> Tuple[list, int]:
        coll = get_annotations_collection()
        query = {}
        if student_id:
            query["student_id"] = student_id
        if is_correct is not None:
            query["is_correct"] = 1 if is_correct else 0
            
        total = coll.count_documents(query)
        cursor = coll.find(query).sort("annotated_at", -1).skip((page - 1) * per_page).limit(per_page)
        return [object_id_to_str(doc) for doc in cursor], total

    @staticmethod
    def get_pending_annotations() -> list:
        """Fetch annotations not yet included in dataset."""
        coll = get_annotations_collection()
        cursor = coll.find({"included_in_dataset": 0}).sort("annotated_at", 1)
        return [object_id_to_str(doc) for doc in cursor]

    @staticmethod
    def mark_included(annotation_id: str) -> bool:
        coll = get_annotations_collection()
        res = coll.update_one(
            {"_id": str_to_object_id(annotation_id)},
            {"$set": {"included_in_dataset": 1}}
        )
        return res.modified_count > 0

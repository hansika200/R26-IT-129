"""
repositories/sign_repository.py
===============================
Repository for Sign collection.

Research Component: SLSL Recognition System — Objective 4
"""

from typing import Optional, Tuple
from database.collections import get_signs_collection
from utils.bson_helper import object_id_to_str, str_to_object_id

class SignRepository:
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"

    @staticmethod
    def create_sign(payload: dict) -> dict:
        coll = get_signs_collection()
        res = coll.insert_one(payload)
        payload['_id'] = res.inserted_id
        return object_id_to_str(payload)

    @staticmethod
    def get_by_id(sign_id: str) -> Optional[dict]:
        coll = get_signs_collection()
        doc = coll.find_one({"_id": str_to_object_id(sign_id)})
        return object_id_to_str(doc)

    @staticmethod
    def list_signs(
        status: Optional[str] = None,
        submitted_by: Optional[str] = None,
        page: int = 1,
        per_page: int = 20
    ) -> Tuple[list, int]:
        coll = get_signs_collection()
        query = {}
        if status:
            query["status"] = status
        if submitted_by:
            query["submitted_by"] = submitted_by
        
        total = coll.count_documents(query)
        cursor = coll.find(query).sort("created_at", -1).skip((page - 1) * per_page).limit(per_page)
        items = [object_id_to_str(doc) for doc in cursor]
        return items, total

    @staticmethod
    def update_status(sign_id: str, status: str, updated_at: str) -> bool:
        coll = get_signs_collection()
        res = coll.update_one(
            {"_id": str_to_object_id(sign_id)},
            {"$set": {"status": status, "updated_at": updated_at}}
        )
        return res.modified_count > 0

    @staticmethod
    def update_keypoints(sign_id: str, path: str, sample_count: int, updated_at: str) -> bool:
        coll = get_signs_collection()
        res = coll.update_one(
            {"_id": str_to_object_id(sign_id)},
            {"$set": {"keypoints_path": path, "sample_count": sample_count, "updated_at": updated_at}}
        )
        return res.modified_count > 0

    @staticmethod
    def mark_in_model(sign_id: str, in_model: bool, updated_at: str) -> bool:
        coll = get_signs_collection()
        res = coll.update_one(
            {"_id": str_to_object_id(sign_id)},
            {"$set": {"is_in_model": 1 if in_model else 0, "updated_at": updated_at}}
        )
        return res.modified_count > 0

    @staticmethod
    def get_stats() -> dict:
        coll = get_signs_collection()
        pipeline = [
            {"$group": {"_id": "$status", "cnt": {"$sum": 1}}}
        ]
        counts = {doc["_id"]: doc["cnt"] for doc in coll.aggregate(pipeline)}
        counts["in_model"] = coll.count_documents({"is_in_model": 1})
        return counts

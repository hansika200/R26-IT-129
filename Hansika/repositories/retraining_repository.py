"""
repositories/retraining_repository.py
=====================================
Repository for Retraining Logs.

Research Component: SLSL Recognition System — Objective 4
"""

from typing import Tuple, Optional
from database.collections import get_retraining_logs_collection, get_signs_collection, get_annotations_collection
from utils.bson_helper import object_id_to_str, str_to_object_id
from datetime import datetime

class RetrainingRepository:
    @staticmethod
    def create_log(payload: dict) -> dict:
        coll = get_retraining_logs_collection()
        res = coll.insert_one(payload)
        payload['_id'] = res.inserted_id
        return object_id_to_str(payload)

    @staticmethod
    def update_log(log_id: str, status: str, model_path: str = "", error: str = "") -> bool:
        coll = get_retraining_logs_collection()
        res = coll.update_one(
            {"_id": str_to_object_id(log_id)},
            {"$set": {
                "status": status,
                "model_path": model_path,
                "error_message": error,
                "completed_at": datetime.utcnow().isoformat()
            }}
        )
        return res.modified_count > 0

    @staticmethod
    def get_log(log_id: str) -> Optional[dict]:
        coll = get_retraining_logs_collection()
        doc = coll.find_one({"_id": str_to_object_id(log_id)})
        return object_id_to_str(doc)

    @staticmethod
    def list_logs(page: int = 1, per_page: int = 20) -> Tuple[list, int]:
        coll = get_retraining_logs_collection()
        total = coll.count_documents({})
        cursor = coll.find({}).sort("started_at", -1).skip((page - 1) * per_page).limit(per_page)
        return [object_id_to_str(doc) for doc in cursor], total

    @staticmethod
    def get_new_approved_signs() -> list:
        coll = get_signs_collection()
        cursor = coll.find({"status": "approved", "is_in_model": 0}, {"_id": 1, "label": 1})
        return [object_id_to_str(doc) for doc in cursor]

    @staticmethod
    def mark_signs_in_model(sign_ids: list, updated_at: str) -> bool:
        coll = get_signs_collection()
        obj_ids = [str_to_object_id(sid) for sid in sign_ids]
        res = coll.update_many(
            {"_id": {"$in": obj_ids}},
            {"$set": {"is_in_model": 1, "updated_at": updated_at}}
        )
        return res.modified_count > 0

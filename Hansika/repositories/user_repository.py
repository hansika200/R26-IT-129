"""
repositories/user_repository.py
===============================
Repository for User collection (teachers/admins).

Research Component: SLSL Recognition System — Objective 4
"""

from typing import Optional
from database.collections import get_users_collection
from utils.bson_helper import object_id_to_str, str_to_object_id

class UserRepository:
    @staticmethod
    def create_user(payload: dict) -> dict:
        """Insert a user document and return the full doc with _id."""
        coll = get_users_collection()
        res = coll.insert_one(payload)
        payload['_id'] = res.inserted_id
        return object_id_to_str(payload)

    @staticmethod
    def get_by_username_or_email(username: str, email: str) -> Optional[dict]:
        coll = get_users_collection()
        doc = coll.find_one({"$or": [{"username": username}, {"email": email}]})
        return object_id_to_str(doc)

    @staticmethod
    def get_by_username(username: str) -> Optional[dict]:
        coll = get_users_collection()
        doc = coll.find_one({"username": username, "is_active": 1})
        return object_id_to_str(doc)

    @staticmethod
    def get_by_id(user_id: str) -> Optional[dict]:
        coll = get_users_collection()
        doc = coll.find_one({"_id": str_to_object_id(user_id)})
        return object_id_to_str(doc)

    @staticmethod
    def list_users(role: Optional[str] = None) -> list:
        coll = get_users_collection()
        query = {}
        if role:
            query["role"] = role
        cursor = coll.find(query).sort("created_at", -1)
        return [object_id_to_str(doc) for doc in cursor]

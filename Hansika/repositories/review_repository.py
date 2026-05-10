"""
repositories/review_repository.py
=================================
Repository for Peer Reviews.

Research Component: SLSL Recognition System — Objective 4
"""

from database.collections import get_peer_reviews_collection
from utils.bson_helper import object_id_to_str, str_to_object_id

class ReviewRepository:
    DECISION_APPROVED = "approved"
    DECISION_REJECTED = "rejected"

    @staticmethod
    def create_review(payload: dict) -> dict:
        coll = get_peer_reviews_collection()
        res = coll.insert_one(payload)
        payload['_id'] = res.inserted_id
        return object_id_to_str(payload)

    @staticmethod
    def list_reviews_for_sign(sign_id: str) -> list:
        coll = get_peer_reviews_collection()
        cursor = coll.find({"sign_id": sign_id}).sort("reviewed_at", -1)
        return [object_id_to_str(doc) for doc in cursor]

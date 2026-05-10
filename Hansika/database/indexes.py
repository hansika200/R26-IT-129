"""
database/indexes.py
===================
Logic to create required MongoDB indexes on startup.

Research Component: SLSL Recognition System — Objective 4
"""

import logging
from pymongo import ASCENDING, DESCENDING

from database.collections import (
    get_users_collection,
    get_signs_collection,
    get_annotations_collection,
    get_assignments_collection,
    get_retraining_logs_collection
)

logger = logging.getLogger(__name__)

def create_indexes():
    """Ensure all required indexes exist in the MongoDB collections."""
    try:
        # Users
        users = get_users_collection()
        users.create_index("username", unique=True)
        users.create_index("email", unique=True)

        # Signs
        signs = get_signs_collection()
        signs.create_index("status")
        signs.create_index("label")
        signs.create_index("submitted_by")

        # Annotations
        annotations = get_annotations_collection()
        annotations.create_index("student_id")
        annotations.create_index("is_correct")
        
        # Assignments
        assignments = get_assignments_collection()
        assignments.create_index("student_group")

        # Retraining Logs
        retraining_logs = get_retraining_logs_collection()
        retraining_logs.create_index([("started_at", DESCENDING)])

        logger.info("MongoDB indexes created/verified successfully.")
    except Exception as e:
        logger.error("Failed to create MongoDB indexes: %s", e)

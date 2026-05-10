"""
database/collections.py
=======================
Helpers to access specific MongoDB collections.

Research Component: SLSL Recognition System — Objective 4
"""

from database.mongodb import get_db

def get_users_collection():
    return get_db().users

def get_signs_collection():
    return get_db().signs

def get_peer_reviews_collection():
    return get_db().peer_reviews

def get_annotations_collection():
    return get_db().annotations

def get_assignments_collection():
    return get_db().assignments

def get_student_progress_collection():
    return get_db().student_progress

def get_retraining_logs_collection():
    return get_db().retraining_logs

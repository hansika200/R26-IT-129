"""
repositories/analytics_repository.py
====================================
Repository for Analytics aggregation.

Research Component: SLSL Recognition System — Objective 4
"""

from datetime import datetime, timedelta
from typing import Optional
from database.collections import (
    get_signs_collection,
    get_annotations_collection,
    get_assignments_collection,
    get_student_progress_collection,
    get_retraining_logs_collection,
    get_db
)
from utils.bson_helper import object_id_to_str

class AnalyticsRepository:
    @staticmethod
    def get_dashboard_summary() -> dict:
        signs = get_signs_collection()
        annotations = get_annotations_collection()
        assignments = get_assignments_collection()
        progress = get_student_progress_collection()
        retraining = get_retraining_logs_collection()

        total_signs = signs.count_documents({})
        pending_signs = signs.count_documents({"status": "pending"})
        approved_signs = signs.count_documents({"status": "approved"})
        
        # Pending annotations: student recordings that aren't annotated.
        # Wait, the old system used 'student_recordings' table where is_annotated=0
        # In MongoDB, annotations collection replaces student_recordings in the new architecture,
        # but let's assume we count something equivalent or we might need a recordings collection.
        # Based on models.py, there was student_recordings. We didn't create a repository for it.
        # Let's count annotations without included_in_dataset? Actually the prompt says:
        # "annotations: ... included_in_dataset".
        # Let's count un-annotated if there's a field for it, or just use 0 for now if structure changed.
        pending_annots = get_db().student_recordings.count_documents({"is_annotated": 0}) if 'student_recordings' in get_db().list_collection_names() else 0

        active_assigns = assignments.count_documents({"is_active": 1})
        unique_students = len(progress.distinct("student_id"))
        retrain_ok = retraining.count_documents({"status": "success"})

        return {
            "vocabulary": {"total": total_signs, "pending": pending_signs, "approved": approved_signs},
            "pending_annotations": pending_annots,
            "active_assignments": active_assigns,
            "unique_students": unique_students,
            "successful_retraining_runs": retrain_ok,
        }

    @staticmethod
    def get_student_performance_overview(assignment_id: Optional[str] = None) -> list:
        progress = get_student_progress_collection()
        match_stage = {}
        if assignment_id:
            match_stage["assignment_id"] = assignment_id

        pipeline = [
            {"$match": match_stage} if match_stage else {"$match": {}},
            {"$group": {
                "_id": "$student_id",
                "avg_score": {"$avg": "$score"},
                "avg_completion": {"$avg": "$completion_pct"},
                "assignment_count": {"$sum": 1},
                "last_activity": {"$max": "$last_activity"}
            }},
            {"$sort": {"avg_score": -1}},
            {"$project": {
                "student_id": "$_id",
                "avg_score": {"$round": ["$avg_score", 1]},
                "avg_completion": {"$round": ["$avg_completion", 1]},
                "assignment_count": 1,
                "last_activity": 1,
                "_id": 0
            }}
        ]
        return list(progress.aggregate(pipeline))

    @staticmethod
    def get_struggling_students(score_threshold: float = 50.0) -> list:
        progress = get_student_progress_collection()
        pipeline = [
            {"$group": {
                "_id": "$student_id",
                "avg_score": {"$avg": "$score"},
                "assignment_count": {"$sum": 1}
            }},
            {"$match": {"avg_score": {"$lt": score_threshold}}},
            {"$sort": {"avg_score": 1}},
            {"$project": {
                "student_id": "$_id",
                "avg_score": {"$round": ["$avg_score", 1]},
                "assignment_count": 1,
                "_id": 0
            }}
        ]
        return list(progress.aggregate(pipeline))

    @staticmethod
    def get_sign_difficulty_report() -> list:
        annotations = get_annotations_collection()
        pipeline = [
            {"$group": {
                "_id": "$correct_label",
                "total_attempts": {"$sum": 1},
                "error_count": {"$sum": {"$cond": [{"$eq": ["$is_correct", 0]}, 1, 0]}}
            }},
            {"$project": {
                "sign_label": "$_id",
                "total_attempts": 1,
                "error_count": 1,
                "error_rate_pct": {
                    "$round": [
                        {"$multiply": [{"$divide": ["$error_count", "$total_attempts"]}, 100]},
                        1
                    ]
                },
                "_id": 0
            }},
            {"$sort": {"error_count": -1}}
        ]
        return list(annotations.aggregate(pipeline))

    @staticmethod
    def get_activity_trend(days: int = 30) -> list:
        # Assuming student_recordings has created_at
        db = get_db()
        if 'student_recordings' not in db.list_collection_names():
            return []
        recordings = db.student_recordings
        cutoff = datetime.utcnow() - timedelta(days=days)
        pipeline = [
            {"$match": {"created_at": {"$gte": cutoff.isoformat()}}},
            {"$project": {
                "date": {"$substr": ["$created_at", 0, 10]}
            }},
            {"$group": {
                "_id": "$date",
                "recording_count": {"$sum": 1}
            }},
            {"$sort": {"_id": 1}},
            {"$project": {"date": "$_id", "recording_count": 1, "_id": 0}}
        ]
        return list(recordings.aggregate(pipeline))

    @staticmethod
    def get_assignment_completion_report() -> list:
        assignments = get_assignments_collection()
        pipeline = [
            {"$match": {"is_active": 1}},
            {"$lookup": {
                "from": "student_progress",
                "localField": "_id",
                "foreignField": "assignment_id",
                "as": "progress"
            }},
            {"$project": {
                "assignment_id": {"$toString": "$_id"},
                "title": 1,
                "student_count": {"$size": "$progress"},
                "avg_score": {"$round": [{"$avg": "$progress.score"}, 1]},
                "avg_completion": {"$round": [{"$avg": "$progress.completion_pct"}, 1]}
            }},
            {"$sort": {"avg_score": -1}}
        ]
        return list(assignments.aggregate(pipeline))

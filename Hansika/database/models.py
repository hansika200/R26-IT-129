"""
database/models.py
==================
Data model helpers — thin wrappers that map database rows to typed
Python dicts, and provide convenience factory methods used by services.

No ORM used intentionally — keeping dependencies minimal and maximising
compatibility with the existing research stack.

Research Component: SLSL Recognition System — Objective 4
Author: Hansika
"""

from datetime import datetime
from typing import Optional


# ── User ─────────────────────────────────────────────────────────────────────

class UserModel:
    """Represents a teacher/admin user."""

    TABLE = "users"

    @staticmethod
    def safe_dict(row: dict) -> dict:
        """Strip password_hash before returning to API consumers."""
        d = dict(row)
        d.pop("password_hash", None)
        return d

    @staticmethod
    def create_payload(
        username: str,
        email: str,
        password_hash: str,
        full_name: str = "",
        role: str = "teacher",
    ) -> dict:
        now = datetime.utcnow().isoformat()
        return {
            "username": username,
            "email": email,
            "password_hash": password_hash,
            "full_name": full_name,
            "role": role,
            "is_active": 1,
            "created_at": now,
            "updated_at": now,
        }


# ── Sign ──────────────────────────────────────────────────────────────────────

class SignModel:
    """Represents a sign/gesture vocabulary entry."""

    TABLE = "signs"
    STATUS_PENDING  = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"

    @staticmethod
    def create_payload(
        label: str,
        submitted_by: int,
        description: str = "",
        video_path: str = "",
        keypoints_path: str = "",
    ) -> dict:
        now = datetime.utcnow().isoformat()
        return {
            "label": label,
            "description": description,
            "video_path": video_path,
            "keypoints_path": keypoints_path,
            "submitted_by": submitted_by,
            "status": SignModel.STATUS_PENDING,
            "sample_count": 0,
            "is_in_model": 0,
            "created_at": now,
            "updated_at": now,
        }


# ── Peer Review ───────────────────────────────────────────────────────────────

class PeerReviewModel:
    """Represents a peer review decision on a submitted sign."""

    TABLE = "peer_reviews"
    DECISION_APPROVED = "approved"
    DECISION_REJECTED = "rejected"

    @staticmethod
    def create_payload(
        sign_id: int,
        reviewer_id: int,
        decision: str,
        rejection_reason: str = "",
        notes: str = "",
    ) -> dict:
        return {
            "sign_id": sign_id,
            "reviewer_id": reviewer_id,
            "decision": decision,
            "rejection_reason": rejection_reason,
            "notes": notes,
            "reviewed_at": datetime.utcnow().isoformat(),
        }


# ── Student Recording ─────────────────────────────────────────────────────────

class StudentRecordingModel:
    """Represents a recording submitted by a student for evaluation."""

    TABLE = "student_recordings"

    @staticmethod
    def create_payload(
        student_id: str,
        sign_label: str,
        video_path: str = "",
        keypoints_path: str = "",
        prediction: str = "",
        confidence: float = 0.0,
    ) -> dict:
        return {
            "student_id": student_id,
            "sign_label": sign_label,
            "video_path": video_path,
            "keypoints_path": keypoints_path,
            "prediction": prediction,
            "confidence": confidence,
            "is_annotated": 0,
            "created_at": datetime.utcnow().isoformat(),
        }


# ── Annotation ────────────────────────────────────────────────────────────────

class AnnotationModel:
    """Represents a teacher annotation of a student recording."""

    TABLE = "annotations"

    @staticmethod
    def create_payload(
        recording_id: int,
        annotated_by: int,
        is_correct: bool,
        correct_label: str = "",
        notes: str = "",
    ) -> dict:
        return {
            "recording_id": recording_id,
            "annotated_by": annotated_by,
            "is_correct": 1 if is_correct else 0,
            "correct_label": correct_label,
            "notes": notes,
            "included_in_dataset": 0,
            "annotated_at": datetime.utcnow().isoformat(),
        }


# ── Assignment ────────────────────────────────────────────────────────────────

class AssignmentModel:
    """Represents a practice assignment created by a teacher."""

    TABLE = "assignments"

    @staticmethod
    def create_payload(
        title: str,
        created_by: int,
        sign_labels: list,
        description: str = "",
        due_date: Optional[str] = None,
    ) -> dict:
        import json
        now = datetime.utcnow().isoformat()
        return {
            "title": title,
            "description": description,
            "created_by": created_by,
            "sign_labels": json.dumps(sign_labels),
            "due_date": due_date,
            "is_active": 1,
            "created_at": now,
            "updated_at": now,
        }


# ── Student Progress ──────────────────────────────────────────────────────────

class StudentProgressModel:
    """Tracks a student's performance on an assignment."""

    TABLE = "student_progress"

    @staticmethod
    def create_payload(
        student_id: str,
        assignment_id: int,
        signs_attempted: list = None,
        signs_correct: list = None,
        score: float = 0.0,
        completion_pct: float = 0.0,
    ) -> dict:
        import json
        return {
            "student_id": student_id,
            "assignment_id": assignment_id,
            "signs_attempted": json.dumps(signs_attempted or []),
            "signs_correct": json.dumps(signs_correct or []),
            "score": score,
            "completion_pct": completion_pct,
            "last_activity": datetime.utcnow().isoformat(),
        }


# ── Retraining Log ────────────────────────────────────────────────────────────

class RetrainingLogModel:
    """Records one AI retraining event."""

    TABLE = "retraining_logs"
    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_SUCCESS = "success"
    STATUS_FAILED  = "failed"

    REASON_MANUAL    = "manual"
    REASON_AUTO      = "auto_threshold"

    @staticmethod
    def create_payload(
        trigger_reason: str,
        triggered_by: Optional[int] = None,
        new_signs: list = None,
        sample_count: int = 0,
    ) -> dict:
        import json
        return {
            "triggered_by": triggered_by,
            "trigger_reason": trigger_reason,
            "new_signs": json.dumps(new_signs or []),
            "sample_count": sample_count,
            "status": RetrainingLogModel.STATUS_PENDING,
            "model_path": "",
            "error_message": "",
            "started_at": datetime.utcnow().isoformat(),
            "finished_at": None,
        }

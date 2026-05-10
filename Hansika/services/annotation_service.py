"""
services/annotation_service.py
================================
Annotation service — teachers label student recordings as
correct/incorrect and provide correction labels.
Now using MongoDB via AnnotationRepository.

Research Component: SLSL Recognition System — Objective 4
"""

import logging
from typing import Optional, Tuple
from datetime import datetime

from repositories.annotation_repository import AnnotationRepository
from database.collections import get_db

logger = logging.getLogger(__name__)

# ── Student recording ingestion ───────────────────────────────────────────────

def ingest_student_recording(
    student_id: str,
    sign_label: str,
    video_path: str = "",
    keypoints_path: str = "",
    prediction: str = "",
    confidence: float = 0.0,
) -> Tuple[bool, str, Optional[dict]]:
    try:
        now = datetime.utcnow().isoformat()
        payload = {
            "student_id": student_id,
            "sign_label": sign_label,
            "video_path": video_path,
            "keypoints_path": keypoints_path,
            "prediction": prediction,
            "confidence": confidence,
            "is_annotated": 0,
            "created_at": now,
        }
        
        coll = get_db().student_recordings
        res = coll.insert_one(payload)
        payload["_id"] = str(res.inserted_id)
        
        return True, "Recording saved for annotation.", payload
    except Exception as exc:
        logger.exception("ingest_student_recording failed: %s", exc)
        return False, f"Failed to save recording: {exc}", None

def list_pending_recordings(page: int = 1, per_page: int = 20) -> Tuple[list, int]:
    try:
        coll = get_db().student_recordings
        total = coll.count_documents({"is_annotated": 0})
        cursor = coll.find({"is_annotated": 0}).sort("created_at", 1).skip((page - 1) * per_page).limit(per_page)
        
        items = []
        for doc in cursor:
            doc["_id"] = str(doc["_id"])
            items.append(doc)
            
        return items, total
    except Exception as exc:
        logger.exception("list_pending_recordings failed: %s", exc)
        return [], 0

# ── Annotation CRUD ───────────────────────────────────────────────────────────

def create_annotation(
    recording_id: str,
    annotated_by: str,
    is_correct: bool,
    correct_label: str = "",
    notes: str = "",
) -> Tuple[bool, str, Optional[dict]]:
    try:
        from utils.bson_helper import str_to_object_id
        rec_coll = get_db().student_recordings
        rec = rec_coll.find_one({"_id": str_to_object_id(recording_id)})
        
        if not rec:
            return False, f"Recording #{recording_id} not found.", None
        if rec.get("is_annotated", 0) == 1:
            return False, "This recording has already been annotated.", None

        payload = {
            "recording_id": recording_id,
            "annotated_by": annotated_by,
            "is_correct": 1 if is_correct else 0,
            "correct_label": correct_label,
            "notes": notes,
            "included_in_dataset": 0,
            "annotated_at": datetime.utcnow().isoformat(),
        }
        ann = AnnotationRepository.create_annotation(payload)

        rec_coll.update_one(
            {"_id": str_to_object_id(recording_id)},
            {"$set": {"is_annotated": 1}}
        )

        logger.info("Annotation#%s saved.", ann["_id"])
        return True, "Annotation saved successfully.", ann

    except Exception as exc:
        logger.exception("create_annotation failed: %s", exc)
        return False, f"Annotation failed: {exc}", None

def list_annotations(
    page: int = 1,
    per_page: int = 20,
    included_in_dataset: Optional[bool] = None,
) -> Tuple[list, int]:
    try:
        return AnnotationRepository.list_annotations(None, included_in_dataset, page, per_page)
    except Exception as exc:
        logger.exception("list_annotations failed: %s", exc)
        return [], 0

def get_annotation_export_data() -> list:
    try:
        annotations = AnnotationRepository.get_pending_annotations()
        export_data = []
        rec_coll = get_db().student_recordings
        from utils.bson_helper import str_to_object_id
        
        for ann in annotations:
            if ann.get("is_correct") == 1:
                rec = rec_coll.find_one({"_id": str_to_object_id(ann["recording_id"])})
                if rec:
                    export_data.append({
                        "id": ann["_id"],
                        "correct_label": ann.get("correct_label"),
                        "keypoints_path": rec.get("keypoints_path"),
                        "sign_label": rec.get("sign_label"),
                        "is_correct": 1,
                        "student_id": rec.get("student_id")
                    })
        return export_data
    except Exception as exc:
        logger.exception("get_annotation_export_data failed: %s", exc)
        return []

def mark_annotations_exported(annotation_ids: list) -> bool:
    if not annotation_ids:
        return True
    try:
        for aid in annotation_ids:
            AnnotationRepository.mark_included(aid)
        return True
    except Exception as exc:
        logger.exception("mark_annotations_exported failed: %s", exc)
        return False

def get_annotation_stats() -> dict:
    try:
        coll = get_db().annotations
        total = coll.count_documents({})
        correct = coll.count_documents({"is_correct": 1})
        pending = get_db().student_recordings.count_documents({"is_annotated": 0})
        exported = coll.count_documents({"included_in_dataset": 1})
        
        return {
            "total_annotations": total,
            "correct": correct,
            "incorrect": total - correct,
            "pending_recordings": pending,
            "exported_to_dataset": exported,
        }
    except Exception as exc:
        logger.exception("get_annotation_stats failed: %s", exc)
        return {}

"""
services/annotation_service.py
================================
Annotation service — teachers label student recordings as
correct/incorrect and provide correction labels.

Annotated data is later fed into the Janith retraining pipeline.

Research Component: SLSL Recognition System — Objective 4
Author: Hansika
"""

import logging
from typing import Optional, Tuple

from database.db import db_context, row_to_dict, rows_to_list
from database.models import AnnotationModel, StudentRecordingModel
from utils.helpers import utcnow_iso

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
    """
    Save a student recording to the database for teacher annotation.

    Called by the Flutter app (or bridged from the existing Janith server)
    whenever a student submits a practice recording.

    Returns:
        (success, message, recording_dict)
    """
    try:
        payload = StudentRecordingModel.create_payload(
            student_id=student_id,
            sign_label=sign_label,
            video_path=video_path,
            keypoints_path=keypoints_path,
            prediction=prediction,
            confidence=confidence,
        )
        with db_context() as conn:
            cursor = conn.execute(
                """INSERT INTO student_recordings
                   (student_id, sign_label, video_path, keypoints_path,
                    prediction, confidence, is_annotated, created_at)
                   VALUES
                   (:student_id, :sign_label, :video_path, :keypoints_path,
                    :prediction, :confidence, :is_annotated, :created_at)""",
                payload,
            )
            rec = row_to_dict(
                conn.execute(
                    "SELECT * FROM student_recordings WHERE id = ?", (cursor.lastrowid,)
                ).fetchone()
            )
        return True, "Recording saved for annotation.", rec
    except Exception as exc:
        logger.exception("ingest_student_recording failed: %s", exc)
        return False, f"Failed to save recording: {exc}", None


def list_pending_recordings(page: int = 1, per_page: int = 20) -> Tuple[list, int]:
    """Return student recordings that haven't been annotated yet."""
    try:
        offset = (page - 1) * per_page
        with db_context() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM student_recordings WHERE is_annotated = 0"
            ).fetchone()[0]
            rows = conn.execute(
                """SELECT * FROM student_recordings
                   WHERE is_annotated = 0
                   ORDER BY created_at ASC
                   LIMIT ? OFFSET ?""",
                (per_page, offset),
            ).fetchall()
        return rows_to_list(rows), total
    except Exception as exc:
        logger.exception("list_pending_recordings failed: %s", exc)
        return [], 0


# ── Annotation CRUD ───────────────────────────────────────────────────────────

def create_annotation(
    recording_id: int,
    annotated_by: int,
    is_correct: bool,
    correct_label: str = "",
    notes: str = "",
) -> Tuple[bool, str, Optional[dict]]:
    """
    Annotate a student recording.

    Business rules:
    - A recording can only be annotated once (first annotation wins).
    - Marks recording.is_annotated = 1 on completion.

    Returns:
        (success, message, annotation_dict)
    """
    try:
        with db_context() as conn:
            # Check recording exists
            rec = conn.execute(
                "SELECT * FROM student_recordings WHERE id = ?", (recording_id,)
            ).fetchone()
            if not rec:
                return False, f"Recording #{recording_id} not found.", None
            if dict(rec)["is_annotated"]:
                return False, "This recording has already been annotated.", None

            payload = AnnotationModel.create_payload(
                recording_id=recording_id,
                annotated_by=annotated_by,
                is_correct=is_correct,
                correct_label=correct_label,
                notes=notes,
            )
            cursor = conn.execute(
                """INSERT INTO annotations
                   (recording_id, annotated_by, is_correct, correct_label,
                    notes, included_in_dataset, annotated_at)
                   VALUES
                   (:recording_id, :annotated_by, :is_correct, :correct_label,
                    :notes, :included_in_dataset, :annotated_at)""",
                payload,
            )
            ann_id = cursor.lastrowid

            # Mark recording as annotated
            conn.execute(
                "UPDATE student_recordings SET is_annotated = 1 WHERE id = ?",
                (recording_id,),
            )

            ann = row_to_dict(
                conn.execute(
                    "SELECT * FROM annotations WHERE id = ?", (ann_id,)
                ).fetchone()
            )

        logger.info(
            "Annotation#%s: recording#%s %s by user#%s",
            ann_id, recording_id,
            "correct" if is_correct else "incorrect",
            annotated_by,
        )
        return True, "Annotation saved successfully.", ann

    except Exception as exc:
        logger.exception("create_annotation failed: %s", exc)
        return False, f"Annotation failed: {exc}", None


def list_annotations(
    page: int = 1,
    per_page: int = 20,
    included_in_dataset: Optional[bool] = None,
) -> Tuple[list, int]:
    """Return all annotations with optional dataset filter."""
    try:
        offset = (page - 1) * per_page
        clause = ""
        params: list = []
        if included_in_dataset is not None:
            clause = "WHERE included_in_dataset = ?"
            params.append(1 if included_in_dataset else 0)

        with db_context() as conn:
            total = conn.execute(
                f"SELECT COUNT(*) FROM annotations {clause}", params
            ).fetchone()[0]
            rows = conn.execute(
                f"""SELECT a.*, sr.sign_label, sr.prediction, sr.student_id,
                           u.username as annotator_name
                    FROM annotations a
                    JOIN student_recordings sr ON a.recording_id = sr.id
                    JOIN users u ON a.annotated_by = u.id
                    {clause}
                    ORDER BY a.annotated_at DESC
                    LIMIT ? OFFSET ?""",
                params + [per_page, offset],
            ).fetchall()
        return rows_to_list(rows), total
    except Exception as exc:
        logger.exception("list_annotations failed: %s", exc)
        return [], 0


def get_annotation_export_data() -> list:
    """
    Return all annotations not yet included in the dataset,
    formatted for export to the Janith training pipeline.
    """
    try:
        with db_context() as conn:
            rows = conn.execute(
                """SELECT a.id, a.correct_label, sr.keypoints_path, sr.sign_label,
                          a.is_correct, sr.student_id
                   FROM annotations a
                   JOIN student_recordings sr ON a.recording_id = sr.id
                   WHERE a.included_in_dataset = 0
                     AND a.is_correct = 1""",
            ).fetchall()
        return rows_to_list(rows)
    except Exception as exc:
        logger.exception("get_annotation_export_data failed: %s", exc)
        return []


def mark_annotations_exported(annotation_ids: list) -> bool:
    """Mark a list of annotation IDs as included in the training dataset."""
    if not annotation_ids:
        return True
    try:
        placeholders = ",".join("?" for _ in annotation_ids)
        with db_context() as conn:
            conn.execute(
                f"UPDATE annotations SET included_in_dataset = 1 WHERE id IN ({placeholders})",
                annotation_ids,
            )
        return True
    except Exception as exc:
        logger.exception("mark_annotations_exported failed: %s", exc)
        return False


def get_annotation_stats() -> dict:
    """Return aggregate annotation statistics."""
    try:
        with db_context() as conn:
            total   = conn.execute("SELECT COUNT(*) FROM annotations").fetchone()[0]
            correct = conn.execute(
                "SELECT COUNT(*) FROM annotations WHERE is_correct = 1"
            ).fetchone()[0]
            pending = conn.execute(
                "SELECT COUNT(*) FROM student_recordings WHERE is_annotated = 0"
            ).fetchone()[0]
            exported = conn.execute(
                "SELECT COUNT(*) FROM annotations WHERE included_in_dataset = 1"
            ).fetchone()[0]
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

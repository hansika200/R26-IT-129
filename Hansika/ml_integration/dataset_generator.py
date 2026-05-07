"""
ml_integration/dataset_generator.py
======================================
Generates labelled training datasets from:
1. Approved teacher sign recordings (keypoints).
2. Correctly annotated student recordings.

Output is compatible with the existing Janith training pipeline format.

Research Component: SLSL Recognition System — Objective 4
Author: Hansika
"""

import logging
from pathlib import Path
from typing import Tuple

import numpy as np

from config.settings import get_config
from database.db import db_context, rows_to_list
from utils.helpers import utcnow_iso

logger = logging.getLogger(__name__)
cfg = get_config()


def export_approved_signs_dataset(output_dir: str) -> Tuple[bool, str, dict]:
    """
    Export keypoint sequences for all approved signs into a flat dataset.

    Each sign's .npy file is copied/concatenated into X (features) and Y (labels).

    Args:
        output_dir: Directory where X.npy and Y.npy will be saved.

    Returns:
        (success, message, {"samples": int, "classes": list})
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    X_samples, Y_labels = [], []

    try:
        with db_context() as conn:
            rows = conn.execute(
                "SELECT label, keypoints_path FROM signs WHERE status='approved' AND keypoints_path != ''"
            ).fetchall()

        signs = rows_to_list(rows)
        if not signs:
            return False, "No approved signs with keypoints available.", {}

        for sign in signs:
            kp_path = Path(sign["keypoints_path"])
            if not kp_path.exists():
                logger.warning("Keypoints file missing: %s", kp_path)
                continue
            try:
                kp = np.load(str(kp_path), allow_pickle=True)
                # Expect shape [N, 30, 63] or [30, 63] for single sample
                if kp.ndim == 2:
                    kp = kp[np.newaxis, ...]   # [1, 30, 63]
                for sample in kp:
                    X_samples.append(sample)
                    Y_labels.append(sign["label"])
            except Exception as exc:
                logger.error("Could not load %s: %s", kp_path, exc)

        if not X_samples:
            return False, "No valid keypoint samples found.", {}

        X = np.array(X_samples, dtype=np.float32)
        Y = np.array(Y_labels)

        np.save(str(output_path / "X.npy"), X)
        np.save(str(output_path / "Y.npy"), Y)

        classes = sorted(set(Y_labels))
        stats = {"samples": len(X_samples), "classes": classes}
        logger.info("Dataset exported: %d samples, %d classes → %s", len(X_samples), len(classes), output_path)
        return True, "Dataset exported successfully.", stats

    except Exception as exc:
        logger.exception("export_approved_signs_dataset failed: %s", exc)
        return False, f"Dataset export failed: {exc}", {}


def export_annotated_student_dataset(output_dir: str) -> Tuple[bool, str, dict]:
    """
    Export keypoint sequences from correctly annotated student recordings.

    Returns:
        (success, message, {"samples": int, "annotation_ids": list})
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    X_samples, Y_labels, ann_ids = [], [], []

    try:
        with db_context() as conn:
            rows = conn.execute(
                """SELECT a.id AS ann_id, a.correct_label, sr.keypoints_path, sr.sign_label
                   FROM annotations a
                   JOIN student_recordings sr ON a.recording_id=sr.id
                   WHERE a.is_correct=1 AND a.included_in_dataset=0
                     AND sr.keypoints_path != ''"""
            ).fetchall()

        records = rows_to_list(rows)
        if not records:
            return False, "No new annotated student recordings to export.", {}

        for rec in records:
            kp_path = Path(rec["keypoints_path"])
            if not kp_path.exists():
                continue
            try:
                kp = np.load(str(kp_path), allow_pickle=True)
                if kp.ndim == 2:
                    kp = kp[np.newaxis, ...]
                for sample in kp:
                    X_samples.append(sample)
                    label = rec["correct_label"] or rec["sign_label"]
                    Y_labels.append(label)
                ann_ids.append(rec["ann_id"])
            except Exception as exc:
                logger.error("Could not load %s: %s", kp_path, exc)

        if not X_samples:
            return False, "No loadable keypoint files found.", {}

        X = np.array(X_samples, dtype=np.float32)
        Y = np.array(Y_labels)
        ts = utcnow_iso().replace(":", "-").replace(".", "-")

        np.save(str(output_path / f"X_student_{ts}.npy"), X)
        np.save(str(output_path / f"Y_student_{ts}.npy"), Y)

        stats = {"samples": len(X_samples), "annotation_ids": ann_ids}
        logger.info("Student dataset exported: %d samples", len(X_samples))
        return True, "Student dataset exported.", stats

    except Exception as exc:
        logger.exception("export_annotated_student_dataset failed: %s", exc)
        return False, f"Export failed: {exc}", {}

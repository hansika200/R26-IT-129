"""
ml_integration/dataset_generator.py
======================================
Generates labelled training datasets from:
1. Approved teacher sign recordings (keypoints).
2. Correctly annotated student recordings.

Output is compatible with the existing Janith training pipeline format.
Now using MongoDB.

Research Component: SLSL Recognition System — Objective 4
Author: Hansika
"""

import logging
from pathlib import Path
from typing import Tuple

import numpy as np

from config.settings import get_config
from database.collections import get_signs_collection, get_annotations_collection, get_db
from utils.bson_helper import str_to_object_id
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
        coll = get_signs_collection()
        signs = list(coll.find({
            "status": "approved",
            "keypoints_path": {"$nin": ["", None]}
        }))

        if not signs:
            return False, "No approved signs with keypoints available.", {}

        for sign in signs:
            kp_path = Path(sign.get("keypoints_path", ""))
            if not str(kp_path) or not kp_path.exists():
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
        ann_coll = get_annotations_collection()
        rec_coll = get_db().student_recordings

        annotations = list(ann_coll.find({"is_correct": 1, "included_in_dataset": 0}))

        if not annotations:
            return False, "No new annotated student recordings to export.", {}

        for ann in annotations:
            rec = rec_coll.find_one({
                "_id": str_to_object_id(ann.get("recording_id")),
                "keypoints_path": {"$nin": ["", None]}
            })

            if not rec:
                continue

            kp_path = Path(rec.get("keypoints_path", ""))
            if not str(kp_path) or not kp_path.exists():
                continue

            try:
                kp = np.load(str(kp_path), allow_pickle=True)
                if kp.ndim == 2:
                    kp = kp[np.newaxis, ...]
                for sample in kp:
                    X_samples.append(sample)
                    label = ann.get("correct_label") or rec.get("sign_label")
                    Y_labels.append(label)
                ann_ids.append(str(ann["_id"]))
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

"""
ml_integration/keypoint_bridge.py
====================================
Bridge into the existing Janith keypoint extraction pipeline.

IMPORTANT: Does NOT modify any Janith files.
Instead, it imports the extract_keypoints logic as a library
and calls it programmatically from within Hansika.

Research Component: SLSL Recognition System — Objective 4
Author: Hansika
"""

import logging
import sys
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

from config.settings import get_config

logger = logging.getLogger(__name__)
cfg = get_config()

# Add Janith training dir to sys.path so we can import its modules
JANITH_TRAINING_DIR = Path(cfg.JANITH_TRAINING_DIR)
if str(JANITH_TRAINING_DIR) not in sys.path:
    sys.path.insert(0, str(JANITH_TRAINING_DIR))


def extract_keypoints_from_video(
    video_path: str,
    output_npy_path: str,
    num_frames: int = 30,
) -> Tuple[bool, str, Optional[str]]:
    """
    Extract MediaPipe hand keypoints from a video file.

    Uses the Janith extract_keypoints pipeline (imported as a module).
    Falls back to a direct MediaPipe call if import fails.

    Args:
        video_path:      Absolute path to the input video.
        output_npy_path: Where to save the resulting .npy file.
        num_frames:      Expected sequence length (default 30).

    Returns:
        (success, message, output_npy_path | None)
    """
    video_path = Path(video_path)
    output_path = Path(output_npy_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not video_path.exists():
        return False, f"Video file not found: {video_path}", None

    try:
        # Prefer importing Janith's extract_keypoints directly
        try:
            import extract_keypoints as ek  # type: ignore
            logger.info("Using Janith extract_keypoints module.")
            # Attempt to call the module's main extraction function
            if hasattr(ek, "extract_from_video"):
                keypoints = ek.extract_from_video(str(video_path), num_frames=num_frames)
            else:
                keypoints = _fallback_extract(str(video_path), num_frames)
        except ImportError:
            logger.warning("Could not import Janith extract_keypoints — using fallback.")
            keypoints = _fallback_extract(str(video_path), num_frames)

        if keypoints is None or len(keypoints) == 0:
            return False, "No keypoints extracted from video.", None

        # Ensure shape [num_frames, 63]
        keypoints = np.array(keypoints, dtype=np.float32)
        if keypoints.ndim == 1:
            keypoints = keypoints.reshape(1, -1)

        np.save(str(output_path), keypoints)
        logger.info("Keypoints saved → %s  shape=%s", output_path, keypoints.shape)
        return True, "Keypoints extracted successfully.", str(output_path)

    except Exception as exc:
        logger.exception("extract_keypoints_from_video failed: %s", exc)
        return False, f"Extraction failed: {exc}", None


def _fallback_extract(video_path: str, num_frames: int = 30) -> Optional[np.ndarray]:
    """
    Fallback keypoint extraction using MediaPipe Hands directly.
    Produces sequences of shape [T, 63] (21 landmarks × 3 axes).
    """
    try:
        import cv2
        import mediapipe as mp

        mp_hands   = mp.solutions.hands
        hands_model = mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.5,
        )

        cap = cv2.VideoCapture(video_path)
        frames_kp = []
        while cap.isOpened() and len(frames_kp) < num_frames * 3:
            ret, frame = cap.read()
            if not ret:
                break
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = hands_model.process(rgb)
            if result.multi_hand_landmarks:
                lm = result.multi_hand_landmarks[0].landmark
                kp = []
                for l in lm:
                    kp.extend([l.x, l.y, l.z])
                frames_kp.append(kp)
            else:
                frames_kp.append([0.0] * 63)  # zero-pad missing frames

        cap.release()
        hands_model.close()

        if len(frames_kp) == 0:
            return None

        # Uniformly sample exactly `num_frames` frames
        indices = np.linspace(0, len(frames_kp) - 1, num_frames, dtype=int)
        sampled = [frames_kp[i] for i in indices]
        return np.array(sampled, dtype=np.float32)

    except Exception as exc:
        logger.exception("_fallback_extract failed: %s", exc)
        return None


def load_classes() -> list:
    """
    Load the existing SLSL class labels from Janith/models/classes.npy.

    Returns:
        List of class label strings.
    """
    classes_path = Path(cfg.JANITH_CLASSES_PATH)
    if not classes_path.exists():
        logger.warning("classes.npy not found at %s", classes_path)
        return []
    try:
        classes = np.load(str(classes_path), allow_pickle=True)
        return list(classes)
    except Exception as exc:
        logger.exception("load_classes failed: %s", exc)
        return []

"""Camera + MediaPipe worker — runs in a QThread, emits signals to the UI.

Uses mediapipe.tasks (0.10+) PoseLandmarker API.
Model file: pose_landmarker_lite.task  (downloaded automatically if absent)
"""
from __future__ import annotations

import time
import urllib.request
from pathlib import Path
from typing import Any

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtGui import QImage

import config
from metrics import add_session_fields, calculate_pose_metrics, no_pose_metrics

# ── Skeleton drawing constants ────────────────────────────────────────────────
# Landmark indices that we care about (PoseLandmark enum values)
_LANDMARK_NAMES = {
    11: "left_shoulder",
    12: "right_shoulder",
    23: "left_hip",
    24: "right_hip",
    25: "left_knee",
    26: "right_knee",
    27: "left_ankle",
    28: "right_ankle",
}

# Key skeleton connections to draw
_CONNECTIONS = [
    (11, 12), (11, 23), (12, 24), (23, 24),   # torso
    (23, 25), (25, 27),                          # left leg
    (24, 26), (26, 28),                          # right leg
    (11, 13), (13, 15),                          # left arm
    (12, 14), (14, 16),                          # right arm
]

# ── Model path ────────────────────────────────────────────────────────────────
MODEL_PATH = Path(__file__).parent / "pose_landmarker_lite.task"
MODEL_URL  = (
    "https://storage.googleapis.com/mediapipe-models/"
    "pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task"
)


def _ensure_model() -> str:
    if not MODEL_PATH.exists():
        print(f"[BioGait] Downloading pose model to {MODEL_PATH} …")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print("[BioGait] Model downloaded.")
    return str(MODEL_PATH)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_landmarks(pose_result) -> dict[str, dict[str, float]]:
    """Convert PoseLandmarker result to the dict format metrics.py expects."""
    if not pose_result.pose_landmarks:
        return {}
    lms = pose_result.pose_landmarks[0]   # first detected person
    out: dict[str, dict[str, float]] = {}
    for idx, name in _LANDMARK_NAMES.items():
        if idx < len(lms):
            lm = lms[idx]
            out[name] = {
                "x":          float(lm.x),
                "y":          float(lm.y),
                "z":          float(lm.z),
                "visibility": float(getattr(lm, "visibility", 1.0)),
            }
    return out


def _draw_skeleton(rgb: Any, pose_result) -> None:
    """Draw skeleton connections + joint dots directly onto an RGB frame."""
    if not pose_result.pose_landmarks:
        return
    lms = pose_result.pose_landmarks[0]
    h, w = rgb.shape[:2]

    def pt(idx):
        lm = lms[idx]
        return int(lm.x * w), int(lm.y * h)

    # connections
    for a, b in _CONNECTIONS:
        if a < len(lms) and b < len(lms):
            cv2.line(rgb, pt(a), pt(b), (0, 230, 100), 2, cv2.LINE_AA)

    # joints
    for idx in _LANDMARK_NAMES:
        if idx < len(lms):
            cv2.circle(rgb, pt(idx), 5, (255, 255, 255), -1, cv2.LINE_AA)
            cv2.circle(rgb, pt(idx), 5, (0, 180, 80),    1,  cv2.LINE_AA)


# ── Worker ────────────────────────────────────────────────────────────────────

class CameraWorker(QObject):
    frame_ready   = pyqtSignal(QImage)
    metrics_ready = pyqtSignal(dict)
    status_ready  = pyqtSignal(str)

    def __init__(self, camera_source: Any) -> None:
        super().__init__()
        self._source   = camera_source
        self._running  = False
        self._session  = time.time()
        self._frame_i  = 0
        self._last_mts = 0.0

    def run(self) -> None:
        self._running = True
        self.status_ready.emit("CONNECTING")

        model_path = _ensure_model()

        base_opts = mp_python.BaseOptions(model_asset_path=model_path)
        opts = mp_vision.PoseLandmarkerOptions(
            base_options=base_opts,
            running_mode=mp_vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        cap = cv2.VideoCapture(self._source)
        if not cap.isOpened():
            self.status_ready.emit("ERROR")
            return

        with mp_vision.PoseLandmarker.create_from_options(opts) as landmarker:
            while self._running:
                ok, frame = cap.read()
                if not ok:
                    self.status_ready.emit("NO_SIGNAL")
                    time.sleep(0.05)
                    continue

                self._frame_i += 1
                if isinstance(self._source, int) and config.MIRROR_LAPTOP_WEBCAM:
                    frame = cv2.flip(frame, 1)

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Build mediapipe Image from frame bytes
                mp_image = mp.Image(
                    image_format=mp.ImageFormat.SRGB,
                    data=rgb,
                )
                ts_ms = int((time.time() - self._session) * 1000)
                result = landmarker.detect_for_video(mp_image, ts_ms)

                if result.pose_landmarks:
                    _draw_skeleton(rgb, result)
                    lms     = _extract_landmarks(result)
                    metrics = calculate_pose_metrics(lms)
                    self.status_ready.emit("TRACKING")
                else:
                    metrics = no_pose_metrics()
                    self.status_ready.emit("NO_POSE")

                elapsed = time.time() - self._session
                metrics = add_session_fields(metrics, self._frame_i, elapsed)

                h, w, ch = rgb.shape
                img = QImage(rgb.tobytes(), w, h, ch * w, QImage.Format_RGB888)
                self.frame_ready.emit(img)

                now = time.time()
                if now - self._last_mts >= 0.25:
                    self.metrics_ready.emit(metrics)
                    self._last_mts = now

        cap.release()

    def stop(self) -> None:
        self._running = False


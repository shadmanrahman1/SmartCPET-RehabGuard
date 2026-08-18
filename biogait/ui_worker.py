"""Camera + MediaPipe worker — runs in a QThread, emits signals to the UI.

Uses mediapipe.tasks (0.10+) PoseLandmarker API.
Model file: pose_landmarker_lite.task  (downloaded automatically if absent)

Engineering notes (M1):
- MediaPipe VIDEO timestamps and timing use a monotonic clock.
- Read failures trigger a bounded NO_SIGNAL -> RECONNECTING cycle.
- Resources are released deterministically (try/finally + context manager).
- Emitted QImage is detached (copy) so it owns its pixel memory.
- Status signals are emitted only on meaningful changes.
"""
from __future__ import annotations

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
from runtime_utils import (
    MonotonicClock,
    ReconnectPolicy,
    StatusGuard,
    interruptible_sleep,
    open_camera,
)

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


def _build_landmarker(model_path: str):
    """Build a VIDEO-mode PoseLandmarker with the project's current settings."""
    base_opts = mp_python.BaseOptions(model_asset_path=model_path)
    opts = mp_vision.PoseLandmarkerOptions(
        base_options=base_opts,
        running_mode=mp_vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=config.POSE_MIN_DETECTION_CONFIDENCE,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=config.POSE_MIN_TRACKING_CONFIDENCE,
    )
    return mp_vision.PoseLandmarker.create_from_options(opts)


# ── Worker ────────────────────────────────────────────────────────────────────

class CameraWorker(QObject):
    frame_ready   = pyqtSignal(QImage)
    metrics_ready = pyqtSignal(dict)
    status_ready  = pyqtSignal(str)

    def __init__(self, camera_source: Any) -> None:
        super().__init__()
        self._source   = camera_source
        self._running  = False
        self._frame_i  = 0
        self._last_mts = 0.0

    def run(self) -> None:
        self._running = True
        status = StatusGuard()
        clock = MonotonicClock()

        def emit_status(new_status: str) -> None:
            if status.update(new_status):
                self.status_ready.emit(new_status)

        emit_status("CONNECTING")

        cap = None
        try:
            model_path = _ensure_model()
            landmarker = _build_landmarker(model_path)

            with landmarker:
                cap = open_camera(self._source)
                if cap is None:
                    print("[BioGait] ERROR: camera could not be opened")
                    emit_status("ERROR")
                    return

                try:
                    self._stream_loop(cap, landmarker, clock, emit_status)
                finally:
                    cap.release()
                    cap = None
        except Exception as exc:
            print(f"[BioGait] ERROR: {type(exc).__name__}: {exc}")
            emit_status("ERROR")
        finally:
            if cap is not None:
                cap.release()
            self._running = False
            emit_status("STOPPED")

    def _stream_loop(self, cap, landmarker, clock, emit_status) -> None:
        reconnect = ReconnectPolicy(
            failure_threshold=config.READ_FAILURE_RECONNECT_THRESHOLD,
            max_reconnect_attempts=config.RECONNECT_MAX_ATTEMPTS,
            base_delay=config.RECONNECT_BASE_DELAY_SECONDS,
            max_delay=config.RECONNECT_MAX_DELAY_SECONDS,
        )

        self._frame_i = 0
        self._last_mts = 0.0

        while self._running:
            ok, frame = cap.read()
            if not ok:
                cap = self._handle_read_failure(cap, reconnect, emit_status)
                continue

            reconnect.on_frame_ok()
            self._frame_i += 1

            if isinstance(self._source, int) and config.MIRROR_LAPTOP_WEBCAM:
                frame = cv2.flip(frame, 1)

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Build mediapipe Image from frame bytes
            mp_image = mp.Image(
                image_format=mp.ImageFormat.SRGB,
                data=rgb,
            )
            ts_ms = clock.video_timestamp_ms()
            result = landmarker.detect_for_video(mp_image, ts_ms)

            if result.pose_landmarks:
                _draw_skeleton(rgb, result)
                lms     = _extract_landmarks(result)
                metrics = calculate_pose_metrics(lms)
                emit_status("TRACKING")
            else:
                metrics = no_pose_metrics()
                emit_status("NO_POSE")

            elapsed = clock.elapsed_seconds()
            metrics = add_session_fields(metrics, self._frame_i, elapsed)

            h, w, ch = rgb.shape
            img = QImage(rgb.tobytes(), w, h, ch * w, QImage.Format_RGB888).copy()
            self.frame_ready.emit(img)

            now = clock.elapsed_seconds()
            if now - self._last_mts >= config.LATEST_WRITE_INTERVAL_SECONDS:
                self.metrics_ready.emit(metrics)
                self._last_mts = now

    def _handle_read_failure(self, cap, reconnect, emit_status):
        """Bounded NO_SIGNAL -> RECONNECTING recovery for failed frame reads."""
        if reconnect.on_frame_failed():
            # Threshold reached: attempt a controlled reconnect.
            if emit_status("RECONNECTING"):
                print("[BioGait] WARN: repeated frame loss — attempting reconnect")
            delay = reconnect.reconnect_delay()
            if delay is None:
                # Bounded attempts exhausted for this stretch; pause, then reset.
                emit_status("NO_SIGNAL")
                interruptible_sleep(
                    config.RECONNECT_PAUSE_RESET_SECONDS, self._should_stop
                )
                reconnect.reset_reconnect()
                return cap
            if not interruptible_sleep(delay, self._should_stop):
                return cap
            emit_status("CONNECTING")
            new_cap = open_camera(self._source)
            if new_cap is not None:
                cap.release()
                cap = new_cap
                emit_status("TRACKING")
            else:
                print("[BioGait] WARN: reconnect failed to reopen camera")
                emit_status("NO_SIGNAL")
            return cap

        emit_status("NO_SIGNAL")
        interruptible_sleep(config.READ_RETRY_PAUSE_SECONDS, self._should_stop)
        return cap

    def _should_stop(self) -> bool:
        return not self._running

    def stop(self) -> None:
        self._running = False


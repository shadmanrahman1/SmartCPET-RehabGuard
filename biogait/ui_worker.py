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
from PyQt5.QtCore import QObject, QThread, pyqtSignal
from PyQt5.QtGui import QImage

import config
from metrics import add_session_fields, calculate_pose_metrics, no_pose_metrics
from evidence_features import build_frame_evidence, extract_world_landmarks
from explanation_ui import evidence_from_payload, run_explanation
from session_controller import BioGaitSessionController
from runtime_utils import (
    MonotonicClock,
    ReconnectPolicy,
    StatusGuard,
    interruptible_sleep,
    make_status_emitter,
    open_camera,
    reconnect_capture,
)
from session_analysis import SessionAccumulator, descriptive_temporal_features

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
        min_pose_presence_confidence=config.POSE_MIN_DETECTION_CONFIDENCE,
        min_tracking_confidence=config.POSE_MIN_TRACKING_CONFIDENCE,
    )
    return mp_vision.PoseLandmarker.create_from_options(opts)


# ── Worker ────────────────────────────────────────────────────────────────────

class CameraWorker(QObject):
    frame_ready   = pyqtSignal(QImage)
    metrics_ready = pyqtSignal(dict)
    status_ready  = pyqtSignal(str)
    evidence_ready = pyqtSignal(dict)

    def __init__(self, camera_source: Any) -> None:
        super().__init__()
        self._source   = camera_source
        self._running  = False
        self._frame_i  = 0
        self._last_mts = 0.0
        # Rolling research-evidence window (display-history only; not a
        # clinical or temporal feature store).
        self._evidence_acc = SessionAccumulator(max_frames=300)
        # Bounded live research-session controller (IDLE/RUNNING/STOPPED).
        self._session = BioGaitSessionController(max_frames=300)
        # Causal-filter observability: raw PO values are never replaced. A live
        # causal filter is only applied when explicitly enabled and rate-validated;
        # by default it stays disabled (REALTIME_FILTER_RATE_VALIDATION=PENDING).
        self._causal_enabled = bool(getattr(config, "BIOGAIT_LIVE_CAUSAL_FILTER", False))
        self._causal_left = None
        self._causal_right = None
        self._last_payload: dict = {}

    def run(self) -> None:
        self._running = True
        status = StatusGuard()
        clock = MonotonicClock()

        emit_status = make_status_emitter(status, self.status_ready.emit)

        emit_status("CONNECTING")

        try:
            model_path = _ensure_model()
            landmarker = _build_landmarker(model_path)

            with landmarker:
                cap = open_camera(self._source)
                if cap is None:
                    print("[BioGait] ERROR: camera could not be opened")
                    emit_status("ERROR")
                    return

                # Ownership of `cap` is transferred to _stream_loop(), which
                # guarantees the currently active capture (including any
                # replacement created during reconnect) is released on exit.
                self._stream_loop(cap, landmarker, clock, emit_status)
        except Exception as exc:
            print(f"[BioGait] ERROR: {type(exc).__name__}: {exc}")
            emit_status("ERROR")
        finally:
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
        self._session.start()

        current_cap = cap  # _stream_loop owns the current capture from here on.
        try:
            while self._running:
                ok, frame = current_cap.read()
                if not ok:
                    current_cap = self._handle_read_failure(
                        current_cap, reconnect, emit_status
                    )
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

                elapsed = clock.elapsed_seconds()

                if result.pose_landmarks:
                    _draw_skeleton(rgb, result)
                    lms     = _extract_landmarks(result)
                    metrics = calculate_pose_metrics(lms)
                    emit_status("TRACKING")

                    # M2 research evidence (world landmarks); legacy metrics
                    # above are left untouched.
                    world = extract_world_landmarks(result)
                    evidence = build_frame_evidence(
                        world, self._frame_i, elapsed
                    )
                else:
                    metrics = no_pose_metrics()
                    emit_status("NO_POSE")
                    # No-pose frames still count toward evidence availability:
                    # an unavailable evidence entry, never fabricated landmarks.
                    evidence = build_frame_evidence({}, self._frame_i, elapsed)

                self._evidence_acc.add(evidence.to_dict())
                self._session.receive_frame_evidence(evidence.to_dict())

                # Causal-filter observability: raw angles are never replaced.
                # Causal output is only shown when explicitly enabled and is never
                # presented as KIMORE reference-equivalent.
                self._update_causal_observability(evidence)

                metrics = add_session_fields(metrics, self._frame_i, elapsed)

                h, w, ch = rgb.shape
                img = QImage(rgb.tobytes(), w, h, ch * w, QImage.Format_RGB888).copy()
                self.frame_ready.emit(img)

                now = clock.elapsed_seconds()
                if now - self._last_mts >= config.LATEST_WRITE_INTERVAL_SECONDS:
                    self.metrics_ready.emit(metrics)
                    self._emit_evidence()
                    self._last_mts = now
        finally:
            self._session.stop()
            if current_cap is not None:
                current_cap.release()

    def _handle_read_failure(self, cap, reconnect, emit_status):
        """Bounded NO_SIGNAL -> RECONNECTING recovery for failed frame reads.

        Delegates the decision to ``reconnect_capture``, which owns `cap`
        for the duration of the attempt and returns the capture that should
        remain current — releasing the old capture if it is replaced.
        """
        def emit_logged(new_status: str) -> bool:
            changed = emit_status(new_status)
            if changed and new_status == "RECONNECTING":
                print("[BioGait] WARN: repeated frame loss — attempting reconnect")
            return changed

        return reconnect_capture(
            reconnect,
            emit_logged,
            lambda: open_camera(self._source),
            interruptible_sleep,
            self._should_stop,
            cap,
            config.READ_RETRY_PAUSE_SECONDS,
            config.RECONNECT_PAUSE_RESET_SECONDS,
        )

    def _should_stop(self) -> bool:
        return not self._running

    def _emit_evidence(self) -> None:
        """Emit a compact research-evidence payload for the UI panel.

        Descriptive only — no clinical scores, pass/fail, or colour semantics.

        Current-state fields come from the LATEST PROCESSED frame (frames[-1]).
        On a NO_POSE frame an older available frame is never substituted, so a
        stale knee angle cannot be displayed as current. Rolling statistics
        (window ROM, rolling PO availability) are computed from the retained
        rolling window and are kept separate from the current frame state.
        """
        frames = self._evidence_acc.frames()
        arrays = self._evidence_acc.aligned_arrays()
        descriptors = descriptive_temporal_features(arrays)

        latest = frames[-1] if frames else None
        latest_quality = latest["quality"] if latest else {}
        if latest:
            latest_left = latest["primary_outcomes"]["left_knee_sagittal_deg"]
            latest_right = latest["primary_outcomes"]["right_knee_sagittal_deg"]
            left_ok = latest_quality.get("left_po_available", False)
            right_ok = latest_quality.get("right_po_available", False)
        else:
            latest_left = latest_right = None
            left_ok = right_ok = False

        # Information-neutral current-PO state (no clinical colour semantics).
        if left_ok and right_ok:
            current_po_state = "complete"
        elif left_ok or right_ok:
            current_po_state = "partial"
        else:
            current_po_state = "unavailable"

        payload = {
            "left_knee_sagittal_deg": latest_left,
            "right_knee_sagittal_deg": latest_right,
            # Current evidence availability = latest frame's PO availability.
            "available": bool(left_ok and right_ok),
            "current_po_state": current_po_state,
            "quality": latest_quality,
            # Rolling window metrics (separate from the current frame state).
            "rolling_po_availability_rate": (
                self._evidence_acc.retained_availability_rate
            ),
            "rolling_left_knee_rom_deg": descriptors.get("left_knee_rom_deg"),
            "rolling_right_knee_rom_deg": descriptors.get("right_knee_rom_deg"),
            # Session state + progress (information-neutral).
            "session_state": self._session_state(),
            "processed_frames": self._processed_frames(),
            "research_elapsed_seconds": self._elapsed_seconds(),
            # Causal-filter observability (raw values are never replaced).
            "causal_left_knee_sagittal_deg": getattr(self, "_causal_left", None),
            "causal_right_knee_sagittal_deg": getattr(self, "_causal_right", None),
            "causal_filter_status": (
                "active" if getattr(self, "_causal_enabled", False)
                else "disabled_realtime_filter_rate_pending"
            ),
            "data_origin": "REAL_VIDEO_MEDIAPIPE",
            "processing_mode": "live_mediapipe",
        }
        self._last_payload = payload
        self.evidence_ready.emit(payload)

    def _session_state(self) -> str:
        session = getattr(self, "_session", None)
        if session is not None:
            return session.state
        return "IDLE"

    def _processed_frames(self) -> int:
        session = getattr(self, "_session", None)
        if session is not None:
            return session.processed_frames
        return getattr(self, "_frame_i", 0)

    def _elapsed_seconds(self):
        session = getattr(self, "_session", None)
        elapsed = getattr(session, "elapsed_seconds", None)
        return round(elapsed, 4) if elapsed is not None else None

    @staticmethod
    def _update_causal_observability(evidence) -> None:
        # Causal live filtering stays disabled by default
        # (REALTIME_FILTER_RATE_VALIDATION=PENDING); raw angles are never
        # replaced. When enabled (config.BIOGAIT_LIVE_CAUSAL_FILTER), a
        # CausalKimoreButterworth at config.FRAME_FPS could be applied here, but
        # only after live sample-rate regularity is validated. Correctness over
        # feature count: default is disabled.
        pass

    def export_research_session(self, session_label: Optional[str] = None) -> dict:
        """Export the current retained research evidence as a versioned envelope."""
        session = getattr(self, "_session", None)
        if session is not None:
            return session.export_research_session(
                data_origin="REAL_VIDEO_MEDIAPIPE",
                processing_mode="live_mediapipe",
                session_label=session_label,
            )
        return {
            "schema_version": "1.0",
            "module": "biogait",
            "exercise": "kimore_ex5_squat",
            "data_origin": "REAL_VIDEO_MEDIAPIPE",
            "processing_mode": "live_mediapipe",
        }

    def latest_evidence_payload(self) -> dict:
        return dict(self._last_payload)

    def stop(self) -> None:
        self._running = False


class ExplanationWorker(QThread):
    """Asynchronous, non-blocking explanation run (never on the capture thread)."""

    result_ready = pyqtSignal(dict)
    finished_ok = pyqtSignal(bool)

    def __init__(self, evidence: dict, force: bool = False, parent=None) -> None:
        super().__init__(parent)
        self._evidence = dict(evidence)
        self._force = force

    def run(self) -> None:
        try:
            audit = run_explanation(self._evidence, force=self._force)
            self.result_ready.emit(audit)
            self.finished_ok.emit(True)
        except Exception:  # noqa: BLE001 - never crash the UI on explanation
            self.finished_ok.emit(False)

    def request_explanation(self) -> None:
        self.start()


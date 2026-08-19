"""BioGait live research session controller (Sprint C, C2; integration-fixed).

A small controller around the evidence accumulator that keeps the Qt capture
worker focused on capture/inference. It manages explicit session state
(IDLE / RUNNING / STOPPED) and safely exports structured research evidence.

Integration fixes:
- elapsed duration uses ``time.monotonic()`` and FREEZES after ``stop()``
  (datetime.now(utc) is used only for the absolute UTC start timestamp).
- full-session ("full") vs rolling-window ("rolling") export are separated:
  the full record holds structured FrameEvidence (never raw images/video) and
  is not silently truncated; if an explicit engineering limit is set, the
  export reports ``session_truncated`` / ``session_frame_limit`` /
  ``exported_frame_count`` instead of hiding the truncation.
- a ``threading.RLock`` protects state transitions and snapshot copies so the
  capture thread can write while the GUI exports; slow filesystem writes are
  done by the caller outside the lock.
- no clinical states; optional ``session_label`` only when the caller supplies
  it (never inferred from a filename).
"""
from __future__ import annotations

import math
import time
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Optional

from evidence_schema import (
    SCHEMA_VERSION,
    session_header,
    validate_evidence_record,
)
from session_analysis import SessionAccumulator

ST_IDLE = "IDLE"
ST_RUNNING = "RUNNING"
ST_STOPPED = "STOPPED"


class BioGaitSessionController:
    """Bounded live-session controller with IDLE/RUNNING/STOPPED states."""

    def __init__(
        self,
        max_frames: Optional[int] = 300,
        max_session_frames: Optional[int] = None,
    ) -> None:
        self._lock = RLock()
        self._max_frames = max_frames
        # Engineering ceiling for the FULL session record (None = unbounded).
        self._max_session_frames = max_session_frames
        self._state = ST_IDLE
        self._rolling = SessionAccumulator(max_frames=max_frames)
        self._session_record: list[dict] = []
        self._session_truncated = False
        self._start_mono: Optional[float] = None
        self._stop_mono: Optional[float] = None
        self._start_iso: Optional[str] = None
        self._session_label: Optional[str] = None

    # ── state ────────────────────────────────────────────────────────────
    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    @property
    def processed_frames(self) -> int:
        with self._lock:
            return self._session_frames()

    def _session_frames(self) -> int:
        return self._rolling.total_added

    @property
    def elapsed_seconds(self) -> Optional[float]:
        with self._lock:
            return self._elapsed_locked()

    def _elapsed_locked(self) -> Optional[float]:
        if self._start_mono is None:
            return None
        if self._state == ST_RUNNING:
            return time.monotonic() - self._start_mono
        if self._state == ST_STOPPED:
            return (self._stop_mono or self._start_mono) - self._start_mono
        return None

    def start(self, session_label: Optional[str] = None) -> None:
        with self._lock:
            if self._state == ST_RUNNING:
                raise ValueError("session already running")
            self._rolling = SessionAccumulator(max_frames=self._max_frames)
            self._session_record = []
            self._session_truncated = False
            self._start_mono = time.monotonic()
            self._stop_mono = None
            self._start_iso = datetime.now(timezone.utc).isoformat()
            self._session_label = session_label
            self._state = ST_RUNNING

    def receive_frame_evidence(self, evidence: dict) -> None:
        with self._lock:
            if self._state != ST_RUNNING:
                raise ValueError(f"cannot receive evidence in state {self._state}")
            validate_evidence_record(evidence)
            self._rolling.add(evidence)
            if self._max_session_frames is None or len(self._session_record) < self._max_session_frames:
                self._session_record.append(dict(evidence))
            else:
                self._session_truncated = True

    def stop(self) -> None:
        with self._lock:
            if self._state == ST_RUNNING:
                self._stop_mono = time.monotonic()
                self._state = ST_STOPPED
            # IDLE / STOPPED -> no-op (never fabricate a completed session).

    def reset(self) -> None:
        with self._lock:
            self._state = ST_IDLE
            self._rolling = SessionAccumulator(max_frames=self._max_frames)
            self._session_record = []
            self._session_truncated = False
            self._start_mono = None
            self._stop_mono = None
            self._start_iso = None
            self._session_label = None

    # ── export ───────────────────────────────────────────────────────────
    def current_summary(self) -> dict:
        with self._lock:
            return {
                "state": self._state,
                "processed_frames": self._session_frames(),
                "retained_frames": self._rolling.retained_frames,
                "retained_availability_rate": self._rolling.retained_availability_rate,
                "elapsed_seconds": (
                    round(self._elapsed_locked(), 4) if self._elapsed_locked() is not None else None
                ),
                "start_iso": self._start_iso,
            }

    def export_research_session(
        self,
        *,
        export_scope: str = "full",
        data_origin: str = "REAL_VIDEO_MEDIAPIPE",
        processing_mode: str = "live_mediapipe",
        exercise: str = "kimore_ex5_squat",
        session_label: Optional[str] = None,
    ) -> dict:
        """Export structured research evidence as a versioned envelope.

        ``export_scope="full"`` exports the full session record (may exceed 300
        frames and is unbounded by default); ``export_scope="rolling"`` exports
        only the last ``max_frames`` display window. No raw frames/images are
        exported. The snapshot is copied under the lock; serialization happens
        in the caller.
        """
        with self._lock:
            envelope = session_header(
                data_origin=data_origin, processing_mode=processing_mode, exercise=exercise
            )
            label = session_label or self._session_label
            if export_scope == "rolling":
                snapshot_arrays = self._rolling.aligned_arrays()
                exported = self._rolling.retained_frames
                rolled = True
            else:
                snapshot_arrays = self._arrays_from_record(self._session_record)
                exported = len(self._session_record)
                rolled = False
            export = {
                **envelope,
                "session_state": self._state,
                "session_scope": export_scope,
                "session_persisted_rolling": rolled,
                "session_truncated": self._session_truncated,
                "session_frame_limit": self._max_session_frames,
                "exported_frame_count": exported,
                "processed_frames": self._session_frames(),
                "start_iso": self._start_iso,
                "elapsed_seconds": (
                    round(self._elapsed_locked(), 4) if self._elapsed_locked() is not None else None
                ),
                "quality_summary": self._rolling_quality_summary(),
                "aligned_arrays": snapshot_arrays,
                "retained_availability_rate": (
                    round(self._rolling.retained_availability_rate, 4)
                    if self._rolling.retained_availability_rate is not None
                    else None
                ),
            }
            if label is not None:
                export["session_label"] = label
        validate_evidence_record(export)
        return export

    def _rolling_quality_summary(self) -> dict:
        available = self._rolling.retained_available_count
        total = self._rolling.retained_frames
        return {
            "retained_available_frames": available,
            "retained_unavailable_frames": self._rolling.retained_unavailable_count,
            "retained_total_frames": total,
            "retained_availability_rate": (
                round(available / total, 4) if total else None
            ),
        }

    @staticmethod
    def _arrays_from_record(record: list[dict]) -> dict:
        """Build aligned arrays from the full structured session record."""
        arrays: dict[str, list[Any]] = {
            "timestamps_s": [],
            "left_knee_sagittal_deg": [],
            "right_knee_sagittal_deg": [],
        }
        for ev in record:
            arrays["timestamps_s"].append(float(ev["timestamp_seconds"]))
            po = ev.get("primary_outcomes") or {}
            arrays["left_knee_sagittal_deg"].append(
                _clean(po.get("left_knee_sagittal_deg"))
            )
            arrays["right_knee_sagittal_deg"].append(
                _clean(po.get("right_knee_sagittal_deg"))
            )
        return arrays


def _clean(v):
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return round(f, 6) if math.isfinite(f) else None

"""BioGait live research session controller (Sprint C, C2).

A small controller around the existing evidence accumulator that keeps the
Qt capture worker focused on capture/inference. It manages explicit session
state (IDLE / RUNNING / STOPPED) and safely exports the current retained or
full session. No clinical states are introduced.

This is a non-Qt, deterministic, testable component. The full-session export
reuses neutral metadata (no raw frames, camera URL, IP, username, absolute
paths, or participant names); an optional ``session_label`` is included only if
the caller supplies it (never inferred from a filename).
"""
from __future__ import annotations

import math
import time
from datetime import datetime, timezone
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

    def __init__(self, max_frames: Optional[int] = 300) -> None:
        self._state = ST_IDLE
        self._accumulator = SessionAccumulator(max_frames=max_frames)
        self._start_wall: Optional[float] = None
        self._processed_frames = 0
        self._start_iso: Optional[str] = None
        self._session_label: Optional[str] = None

    # ── state ────────────────────────────────────────────────────────────
    @property
    def state(self) -> str:
        return self._state

    @property
    def processed_frames(self) -> int:
        return self._processed_frames

    @property
    def elapsed_seconds(self) -> Optional[float]:
        if self._start_wall is None:
            return None
        return time.time() - self._start_wall

    def start(self, session_label: Optional[str] = None) -> None:
        if self._state == ST_RUNNING:
            raise ValueError("session already running")
        self._accumulator = SessionAccumulator(max_frames=self._accumulator._max_frames)
        self._processed_frames = 0
        self._start_wall = time.time()
        self._start_iso = datetime.now(timezone.utc).isoformat()
        self._session_label = session_label
        self._state = ST_RUNNING

    def receive_frame_evidence(self, evidence: dict) -> None:
        if self._state != ST_RUNNING:
            raise ValueError(f"cannot receive evidence in state {self._state}")
        validate_evidence_record(evidence)
        self._accumulator.add(evidence)
        self._processed_frames = self._accumulator.total_added

    def stop(self) -> None:
        if self._state != ST_STOPPED:
            self._state = ST_STOPPED

    def reset(self) -> None:
        self._state = ST_IDLE
        self._accumulator = SessionAccumulator(max_frames=self._accumulator._max_frames)
        self._processed_frames = 0
        self._start_wall = None
        self._start_iso = None
        self._session_label = None

    # ── export ───────────────────────────────────────────────────────────
    def current_summary(self) -> dict:
        return {
            "state": self._state,
            "processed_frames": self._processed_frames,
            "retained_frames": self._accumulator.retained_frames,
            "retained_availability_rate": self._accumulator.retained_availability_rate,
            "elapsed_seconds": (
                round(self.elapsed_seconds, 4) if self.elapsed_seconds is not None else None
            ),
            "start_iso": self._start_iso,
        }

    def export_research_session(
        self,
        *,
        data_origin: str = "REAL_VIDEO_MEDIAPIPE",
        processing_mode: str = "live_mediapipe",
        exercise: str = "kimore_ex5_squat",
        session_label: Optional[str] = None,
    ) -> dict:
        """Export current retained research evidence as a versioned envelope.

        ``session_label`` is included ONLY if supplied by the user; it is never
        inferred from a camera/filename. Raw frames are not exported.
        """
        envelope = session_header(
            data_origin=data_origin, processing_mode=processing_mode, exercise=exercise
        )
        label = session_label or self._session_label
        export = {
            **envelope,
            "session_state": self._state,
            "start_iso": self._start_iso,
            "processed_frames": self._processed_frames,
            "elapsed_seconds": (
                round(self.elapsed_seconds, 4) if self.elapsed_seconds is not None else None
            ),
            "quality_summary": self._retained_quality_summary(),
            "aligned_arrays": self._retained_aligned_arrays(),
            "retained_availability_rate": (
                round(self._accumulator.retained_availability_rate, 4)
                if self._accumulator.retained_availability_rate is not None
                else None
            ),
        }
        if session_label is not None:
            export["session_label"] = session_label
        elif label is not None:
            export["session_label"] = label
        validate_evidence_record(export)
        return export

    def _retained_quality_summary(self) -> dict:
        available = self._accumulator.retained_available_count
        total = self._accumulator.retained_frames
        return {
            "retained_available_frames": available,
            "retained_unavailable_frames": self._accumulator.retained_unavailable_count,
            "retained_total_frames": total,
            "retained_availability_rate": (
                round(available / total, 4) if total else None
            ),
        }

    def _retained_aligned_arrays(self) -> dict:
        arrays = self._accumulator.aligned_arrays()
        out = {}
        for key, values in arrays.items():
            out[key] = [None if v is None else (round(v, 6) if _is_num(v) else v) for v in values]
        return out


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v))

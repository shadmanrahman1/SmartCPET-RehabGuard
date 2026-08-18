"""Pure engineering helpers for the BioGait runtime.

This module intentionally contains NO clinical/scientific scoring logic.
All constants here are ENGINEERING RUNTIME SETTINGS, not clinical thresholds.

It provides small, unit-testable primitives used by ui_worker.py:
- monotonic timing (never depends on wall-clock adjustments)
- status-transition guard (avoid flooding the UI)
- bounded reconnect/backoff policy
- camera-open helper
- interruptible sleep (so stop() can interrupt promptly)
"""
from __future__ import annotations

import math
import platform
import sys
import time
from typing import Any, Callable, Optional


SLEEP_CHUNK_SECONDS = 0.05


def _is_windows() -> bool:
    """Report whether we are on a Windows platform (e.g. win32, cygwin)."""
    return sys.platform.startswith("win") or platform.system() == "Windows"


def _cv2():
    """Import cv2 lazily so the rest of this module stays importable and
    unit-testable without OpenCV installed."""
    import cv2

    return cv2


# ── Monotonic timing ───────────────────────────────────────────────────────────

class MonotonicClock:
    """Monotonic time base for session elapsed time and MediaPipe timestamps.

    Uses ``time.perf_counter()`` so values never depend on wall-clock
    adjustments (NTP sync, manual clock changes, etc.).
    """

    def __init__(self) -> None:
        self._start = time.perf_counter()
        self._last_video_ms = -1

    def elapsed_seconds(self) -> float:
        """Session elapsed time in seconds (monotonic, non-negative)."""
        return time.perf_counter() - self._start

    def video_timestamp_ms(self) -> int:
        """Strictly increasing millisecond timestamp for MediaPipe VIDEO mode.

        Guarantees the returned value is at least ``previous + 1`` so it
        never decreases and always satisfies MediaPipe's strictly-increasing
        requirement for ``detect_for_video``.
        """
        current_ms = int(self.elapsed_seconds() * 1000)
        if current_ms <= self._last_video_ms:
            current_ms = self._last_video_ms + 1
        self._last_video_ms = current_ms
        return current_ms


# ── Status transition guard ────────────────────────────────────────────────────

class StatusGuard:
    """Only reports status *changes* so the UI is not flooded with
    identical status strings on every frame."""

    def __init__(self, initial: Optional[str] = None) -> None:
        self._current = initial

    def update(self, new_status: str) -> bool:
        """Return True only when the status meaningfully changed."""
        if new_status != self._current:
            self._current = new_status
            return True
        return False

    @property
    def current(self) -> Optional[str]:
        return self._current


# ── Reconnect / backoff policy ─────────────────────────────────────────────────

class ReconnectPolicy:
    """Bounded exponential backoff for camera read failures and reconnects.

    Engineering runtime settings only — NOT clinical thresholds.
    """

    def __init__(
        self,
        failure_threshold: int = 10,
        max_reconnect_attempts: int = 5,
        base_delay: float = 0.2,
        max_delay: float = 2.0,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.max_reconnect_attempts = max_reconnect_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self._failures = 0
        self._reconnects = 0

    def on_frame_ok(self) -> None:
        """Reset counters after a successful frame."""
        self._failures = 0
        self._reconnects = 0

    def on_frame_failed(self) -> bool:
        """Count a failed frame; return True when a reconnect is required."""
        self._failures += 1
        return self._failures >= self.failure_threshold

    def reconnect_delay(self) -> Optional[float]:
        """Start a reconnect attempt and return the backoff delay to wait.

        Returns None once ``max_reconnect_attempts`` is reached so the
        caller can pause/reset instead of tight-looping forever.
        """
        if self._reconnects >= self.max_reconnect_attempts:
            return None
        delay = min(self.base_delay * (2 ** self._reconnects), self.max_delay)
        self._reconnects += 1
        return delay

    def reset_reconnect(self) -> None:
        """Reset reconnect-attempt counting (used after a pause)."""
        self._reconnects = 0

    @property
    def failed_frames(self) -> int:
        return self._failures

    @property
    def reconnect_attempts(self) -> int:
        return self._reconnects


# ── Camera-open helper ─────────────────────────────────────────────────────────

def open_camera(source: Any) -> Optional["cv2.VideoCapture"]:
    """Open a camera source, or return None if it cannot be opened.

    - Integer index (webcam): on Windows, try ``CAP_DSHOW`` first, then fall
      back to the default backend. On non-Windows, use the default backend
      directly.
    - String URL/IP source: use the default backend.
    """
    cv2 = _cv2()
    if isinstance(source, int) and _is_windows():
        dshow = getattr(cv2, "CAP_DSHOW", None)
        if dshow is not None:
            cap = cv2.VideoCapture(source, dshow)
            if cap.isOpened():
                return cap
            cap.release()
        cap = cv2.VideoCapture(source)
    else:
        cap = cv2.VideoCapture(source)

    if not cap.isOpened():
        cap.release()
        return None
    return cap


# ── Status emitter (dedup + return value) ─────────────────────────────────────

def make_status_emitter(guard: StatusGuard, emit: Callable[[str], None]) -> Callable[[str], bool]:
    """Wrap a status emission callback with deduplication.

    The returned callable calls ``emit(status)`` only when ``guard`` reports a
    real status change, and returns True when the status actually changed.
    """

    def emit_status(new_status: str) -> bool:
        changed = guard.update(new_status)
        if changed:
            emit(new_status)
        return changed

    return emit_status


# ── Reconnect / capture ownership ──────────────────────────────────────────────

def reconnect_capture(
    reconnect: ReconnectPolicy,
    emit: Callable[[str], bool],
    open_camera_fn: Callable[[], Any],
    sleep_fn: Callable[[float, Callable[[], bool]], bool],
    stop_fn: Callable[[], bool],
    cap: Any,
    retry_pause_seconds: float,
    pause_reset_seconds: float,
) -> Any:
    """Handle one failed frame read with bounded reconnect recovery.

    Takes ownership of ``cap`` for the duration of this call and returns the
    capture that should remain the *current* capture afterwards:

    - Transient failure (below threshold): emits ``NO_SIGNAL``, sleeps
      ``retry_pause_seconds``, returns ``cap`` unchanged.
    - At the failure threshold: emits ``RECONNECTING``, backs off, then
      attempts ``open_camera_fn()``. On success the old capture is released
      and the replacement is returned. On failure ``NO_SIGNAL`` is emitted and
      the current capture is returned unchanged.
    - Exhausted reconnect attempts: pauses ``pause_reset_seconds``, resets the
      reconnect counter, returns the current capture unchanged.

    The caller is responsible for releasing the returned capture when the
    stream/loop exits — including any replacement obtained during a reconnect.
    """
    if reconnect.on_frame_failed():
        emit("RECONNECTING")
        delay = reconnect.reconnect_delay()
        if delay is None:
            # Bounded attempts exhausted for this stretch; pause, then reset.
            emit("NO_SIGNAL")
            if not sleep_fn(pause_reset_seconds, stop_fn):
                return cap
            reconnect.reset_reconnect()
            return cap
        if not sleep_fn(delay, stop_fn):
            return cap
        emit("CONNECTING")
        new_cap = open_camera_fn()
        if new_cap is not None:
            cap.release()
            cap = new_cap
            # Reopen success only means frames may become available. The next
            # frame read decides TRACKING / NO_POSE / NO_SIGNAL.
        else:
            emit("NO_SIGNAL")
        return cap

    emit("NO_SIGNAL")
    sleep_fn(retry_pause_seconds, stop_fn)
    return cap


# ── Interruptible sleep ────────────────────────────────────────────────────────

def interruptible_sleep(seconds: float, should_stop: Callable[[], bool]) -> bool:
    """Sleep up to ``seconds`` in small chunks so a stop request can interrupt.

    Returns True if the full duration elapsed, False if ``should_stop()``
    became True during the wait.
    """
    deadline = time.monotonic() + max(0.0, seconds)
    while True:
        if should_stop():
            return False
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return True
        time.sleep(min(SLEEP_CHUNK_SECONDS, remaining))


# ── Source-video timeline (offline, deterministic) ────────────────────────────

class SourceVideoTimeline:
    """Deterministic source-video timeline helper (offline analysis).

    Derives every timestamp from the SOURCE VIDEO frame rate:

    - ``timestamp_seconds(frame_index) = frame_index / fps``
    - ``video_timestamp_ms(frame_index)`` is the rounded millisecond
      timestamp, guaranteed to be strictly increasing numerically.

    It never uses processing wall-clock time as the video timeline. Processing
    wall time remains appropriate only for runtime benchmarking, not for
    source-video scientific timing.
    """

    def __init__(self, fps: float) -> None:
        if not (math.isfinite(fps) and fps > 0):  # rejects 0, negative, NaN, inf
            raise ValueError("fps must be a positive finite number")
        self.fps = float(fps)
        self._prev_ms = -1

    def timestamp_seconds(self, frame_index: int) -> float:
        return frame_index / self.fps

    def video_timestamp_ms(self, frame_index: int) -> int:
        """Millisecond VIDEO timestamp, strictly increasing per call sequence."""
        ts_ms = round(self.timestamp_seconds(frame_index) * 1000)
        ts_ms = max(ts_ms, self._prev_ms + 1)
        self._prev_ms = ts_ms
        return ts_ms
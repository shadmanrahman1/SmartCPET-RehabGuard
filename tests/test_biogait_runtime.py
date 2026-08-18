"""
Tests for biogait/runtime_utils.py — pure engineering helpers.

These tests require NO webcam, NO phone, NO MediaPipe model download,
NO hardware, and NO GUI display. They use mocks where needed.

They do NOT assert anything about clinical/medical validity of thresholds.
"""
from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path
from unittest import mock

# Make biogait importable from tests/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "biogait"))

from runtime_utils import (  # noqa: E402
    MonotonicClock,
    ReconnectPolicy,
    StatusGuard,
    interruptible_sleep,
    open_camera,
)


# ── Monotonic timing ───────────────────────────────────────────────────────────

class MonotonicClockTests(unittest.TestCase):
    def test_elapsed_seconds_never_decreases(self):
        clock = MonotonicClock()
        prev = -1.0
        for _ in range(500):
            value = clock.elapsed_seconds()
            self.assertGreaterEqual(value, prev)
            prev = value

    def test_video_timestamp_strictly_increasing(self):
        clock = MonotonicClock()
        samples = [clock.video_timestamp_ms() for _ in range(500)]
        for i in range(1, len(samples)):
            self.assertGreaterEqual(samples[i], samples[i - 1] + 1)

    def test_video_timestamp_nonnegative(self):
        clock = MonotonicClock()
        for _ in range(200):
            self.assertGreaterEqual(clock.video_timestamp_ms(), 0)


# ── Status guard ───────────────────────────────────────────────────────────────

class StatusGuardTests(unittest.TestCase):
    def test_initial_status_is_none(self):
        self.assertIsNone(StatusGuard().current)

    def test_repeated_identical_status_not_reported(self):
        guard = StatusGuard()
        self.assertTrue(guard.update("TRACKING"))
        self.assertFalse(guard.update("TRACKING"))
        self.assertFalse(guard.update("TRACKING"))

    def test_state_transition_is_reported(self):
        guard = StatusGuard()
        guard.update("TRACKING")
        self.assertTrue(guard.update("NO_POSE"))
        self.assertEqual(guard.current, "NO_POSE")


# ── Camera open helper ─────────────────────────────────────────────────────────

def _fake_cv2(vc_side_effect):
    fake_cv2 = mock.Mock()
    fake_cv2.CAP_DSHOW = 700
    fake_cv2.VideoCapture = mock.Mock(side_effect=vc_side_effect)
    return fake_cv2


class OpenCameraTests(unittest.TestCase):
    @mock.patch("runtime_utils._cv2")
    def test_integer_webcam_prefers_dshow(self, mock_cv2_loader):
        dshow_cap = mock.Mock()
        dshow_cap.isOpened.return_value = True
        mock_cv2_loader.return_value = _fake_cv2(
            lambda source, backend=None: dshow_cap
        )

        cap = open_camera(0)

        self.assertIs(cap, dshow_cap)
        vc = mock_cv2_loader.return_value.VideoCapture
        self.assertEqual(vc.call_count, 1)
        args = vc.call_args[0]
        self.assertEqual(args[0], 0)     # source index
        self.assertEqual(args[1], 700)   # CAP_DSHOW attempted first

    @mock.patch("runtime_utils._cv2")
    def test_integer_webcam_falls_back_when_dshow_fails(self, mock_cv2_loader):
        dshow_cap = mock.Mock()
        dshow_cap.isOpened.return_value = False
        default_cap = mock.Mock()
        default_cap.isOpened.return_value = True

        def _side_effect(source, backend=None):
            if backend == 700:
                return dshow_cap
            return default_cap

        mock_cv2_loader.return_value = _fake_cv2(_side_effect)

        cap = open_camera(0)

        self.assertIs(cap, default_cap)
        vc = mock_cv2_loader.return_value.VideoCapture
        self.assertEqual(vc.call_count, 2)
        dshow_cap.release.assert_called_once()

    @mock.patch("runtime_utils._cv2")
    def test_url_source_uses_default_backend(self, mock_cv2_loader):
        url = "http://192.168.0.105:8080/video"
        url_cap = mock.Mock()
        url_cap.isOpened.return_value = True
        mock_cv2_loader.return_value = _fake_cv2(
            lambda source, backend=None: url_cap
        )

        cap = open_camera(url)

        self.assertIs(cap, url_cap)
        vc = mock_cv2_loader.return_value.VideoCapture
        vc.assert_called_once_with(url)

    @mock.patch("runtime_utils._cv2")
    def test_returns_none_when_all_attempts_fail(self, mock_cv2_loader):
        dshow_cap = mock.Mock()
        dshow_cap.isOpened.return_value = False
        default_cap = mock.Mock()
        default_cap.isOpened.return_value = False

        def _side_effect(source, backend=None):
            if backend == 700:
                return dshow_cap
            return default_cap

        mock_cv2_loader.return_value = _fake_cv2(_side_effect)

        cap = open_camera(0)

        self.assertIsNone(cap)
        vc = mock_cv2_loader.return_value.VideoCapture
        self.assertEqual(vc.call_count, 2)


# ── Reconnect / backoff policy ─────────────────────────────────────────────────

class ReconnectPolicyTests(unittest.TestCase):
    def test_reconnect_triggered_after_failure_threshold(self):
        policy = ReconnectPolicy(failure_threshold=3, max_reconnect_attempts=2)
        for _ in range(2):
            self.assertFalse(policy.on_frame_failed())
        self.assertTrue(policy.on_frame_failed())
        self.assertEqual(policy.failed_frames, 3)

    def test_backoff_is_bounded_and_not_infinite(self):
        policy = ReconnectPolicy(
            failure_threshold=1,
            max_reconnect_attempts=4,
            base_delay=0.1,
            max_delay=0.3,
        )
        expected = [0.1, 0.2, 0.3, 0.3]
        for exp in expected:
            self.assertEqual(policy.reconnect_delay(), exp)
        # Attempts exhausted — no more reconnects (no infinite tight loop).
        self.assertIsNone(policy.reconnect_delay())

    def test_on_frame_ok_resets_failure_and_reconnect_state(self):
        policy = ReconnectPolicy(failure_threshold=2, max_reconnect_attempts=1)
        policy.on_frame_failed()
        policy.on_frame_failed()
        self.assertTrue(policy.on_frame_failed() or policy.failed_frames >= 2)
        policy.reconnect_delay()
        self.assertEqual(policy.reconnect_attempts, 1)

        policy.on_frame_ok()
        self.assertEqual(policy.failed_frames, 0)
        self.assertEqual(policy.reconnect_attempts, 0)


# ── Interruptible sleep ────────────────────────────────────────────────────────

class InterruptibleSleepTests(unittest.TestCase):
    def test_full_wait_completes_when_not_stopped(self):
        start = time.monotonic()
        result = interruptible_sleep(0.02, lambda: False)
        self.assertTrue(result)
        self.assertGreaterEqual(time.monotonic() - start, 0.02)

    def test_stop_request_interrupts_wait_promptly(self):
        start = time.monotonic()
        result = interruptible_sleep(10.0, lambda: True)
        self.assertFalse(result)
        self.assertLess(time.monotonic() - start, 1.0)


if __name__ == "__main__":
    unittest.main()
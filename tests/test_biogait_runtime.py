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
    make_status_emitter,
    open_camera,
    reconnect_capture,
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


# ── Status emitter (dedup + return value) ─────────────────────────────────────
#
# Regression: the worker's emit_status callback must return True on a real
# transition and False on a duplicate, so logging on a meaningful transition
# works.

class StatusEmitterTests(unittest.TestCase):
    def test_returns_true_on_real_transition(self):
        guard = StatusGuard()
        emitted: list[str] = []
        emit_status = make_status_emitter(guard, emitted.append)

        self.assertTrue(emit_status("CONNECTING"))
        self.assertEqual(emitted, ["CONNECTING"])

    def test_returns_false_on_duplicate_status(self):
        guard = StatusGuard()
        emitted: list[str] = []
        emit_status = make_status_emitter(guard, emitted.append)

        emit_status("TRACKING")
        self.assertFalse(emit_status("TRACKING"))
        self.assertFalse(emit_status("TRACKING"))
        # Duplicates are not emitted again.
        self.assertEqual(emitted, ["TRACKING"])

    def test_returns_true_on_transition_and_emits_once(self):
        guard = StatusGuard()
        emitted: list[str] = []
        emit_status = make_status_emitter(guard, emitted.append)

        emit_status("TRACKING")
        self.assertTrue(emit_status("NO_POSE"))
        self.assertTrue(emit_status("NO_SIGNAL"))
        # Emits only real changes, in order.
        self.assertEqual(emitted, ["TRACKING", "NO_POSE", "NO_SIGNAL"])


# ── Camera open helper ─────────────────────────────────────────────────────────

def _fake_cv2(vc_side_effect):
    fake_cv2 = mock.Mock()
    fake_cv2.CAP_DSHOW = 700
    fake_cv2.VideoCapture = mock.Mock(side_effect=vc_side_effect)
    return fake_cv2


class OpenCameraTests(unittest.TestCase):
    @mock.patch("runtime_utils._is_windows", return_value=True)
    @mock.patch("runtime_utils._cv2")
    def test_windows_integer_webcam_prefers_dshow(self, mock_cv2_loader, _mock_win):
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

    @mock.patch("runtime_utils._is_windows", return_value=True)
    @mock.patch("runtime_utils._cv2")
    def test_windows_integer_webcam_falls_back_when_dshow_fails(
        self, mock_cv2_loader, _mock_win
    ):
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

    @mock.patch("runtime_utils._is_windows", return_value=False)
    @mock.patch("runtime_utils._cv2")
    def test_non_windows_integer_source_uses_default_backend_directly(
        self, mock_cv2_loader, _mock_win
    ):
        default_cap = mock.Mock()
        default_cap.isOpened.return_value = True
        mock_cv2_loader.return_value = _fake_cv2(
            lambda source, backend=None: default_cap
        )

        cap = open_camera(0)

        self.assertIs(cap, default_cap)
        vc = mock_cv2_loader.return_value.VideoCapture
        self.assertEqual(vc.call_count, 1)
        # Only the default call, with no backend argument.
        args = vc.call_args[0]
        self.assertEqual(len(args), 1)
        self.assertEqual(args[0], 0)

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

    @mock.patch("runtime_utils._is_windows", return_value=True)
    @mock.patch("runtime_utils._cv2")
    def test_windows_returns_none_when_all_attempts_fail(
        self, mock_cv2_loader, _mock_win
    ):
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


# ── Reconnect / capture ownership regression ───────────────────────────────────
#
# Regression: reopening a camera must NOT report TRACKING merely because the
# capture reopened; and capture ownership must move cleanly — the original
# capture is released when replaced, and the replacement is what the caller
# must release on exit.

def _noop_sleep(_seconds, _stop) -> bool:
    return True


class ReconnectCaptureTests(unittest.TestCase):
    def test_reconnect_success_does_not_emit_tracking(self):
        reconnect = ReconnectPolicy(
            failure_threshold=1, max_reconnect_attempts=3, base_delay=0.1,
            max_delay=0.2,
        )
        old_cap = mock.Mock()
        new_cap = mock.Mock()
        emitted: list[str] = []

        def emit(status):
            emitted.append(status)
            return True

        result = reconnect_capture(
            reconnect, emit, lambda: new_cap, _noop_sleep, lambda: False,
            old_cap, retry_pause_seconds=0.05, pause_reset_seconds=1.0,
        )

        # A reopen only makes frames *potentially* available — never TRACKING.
        self.assertNotIn("TRACKING", emitted)
        self.assertIn("CONNECTING", emitted)
        self.assertIn("RECONNECTING", emitted)
        self.assertIs(result, new_cap)

    def test_reconnect_releases_original_when_replaced(self):
        reconnect = ReconnectPolicy(
            failure_threshold=1, max_reconnect_attempts=3, base_delay=0.1,
            max_delay=0.2,
        )
        old_cap = mock.Mock()
        new_cap = mock.Mock()

        result = reconnect_capture(
            reconnect, lambda s: True, lambda: new_cap, _noop_sleep,
            lambda: False, old_cap,
            retry_pause_seconds=0.05, pause_reset_seconds=1.0,
        )

        old_cap.release.assert_called_once()
        self.assertIs(result, new_cap)

    def test_reconnect_failure_keeps_current_and_emits_no_signal(self):
        reconnect = ReconnectPolicy(
            failure_threshold=1, max_reconnect_attempts=3, base_delay=0.1,
            max_delay=0.2,
        )
        old_cap = mock.Mock()
        emitted: list[str] = []

        result = reconnect_capture(
            reconnect, emitted.append, lambda: None, _noop_sleep,
            lambda: False, old_cap,
            retry_pause_seconds=0.05, pause_reset_seconds=1.0,
        )

        self.assertNotIn("TRACKING", emitted)
        self.assertIn("NO_SIGNAL", emitted)
        old_cap.release.assert_not_called()
        self.assertIs(result, old_cap)

    def test_transient_failure_emits_no_signal_and_keeps_cap(self):
        reconnect = ReconnectPolicy(
            failure_threshold=5, max_reconnect_attempts=3, base_delay=0.1,
            max_delay=0.2,
        )
        cap = mock.Mock()
        emitted: list[str] = []

        result = reconnect_capture(
            reconnect, emitted.append, lambda: None, _noop_sleep,
            lambda: False, cap,
            retry_pause_seconds=0.05, pause_reset_seconds=1.0,
        )

        self.assertEqual(emitted, ["NO_SIGNAL"])
        cap.release.assert_not_called()
        self.assertIs(result, cap)


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


# ── Worker capture ownership (reconnect lifecycle) ─────────────────────────────
#
# Regression: _stream_loop() owns the current capture, including a replacement
# obtained during reconnect. The original capture is released when replaced,
# and the replacement/current capture is released when the stream exits.

import types as _types  # noqa: E402


def _install_ui_worker_stubs():
    """Install lightweight sys.modules stubs so ui_worker can be imported and
    its ownership logic tested without cv2 / mediapipe / PyQt5 installed.
    These shadows are sufficient for exercising _stream_loop() internals; no
    real hardware, model download, or GUI display is involved."""
    qt_core = _types.ModuleType("PyQt5.QtCore")
    qt_core.QObject = type("QObjectStub", (), {})
    qt_core.QThread = type("QThreadStub", (), {})
    qt_core.pyqtSignal = lambda *a, **k: mock.MagicMock()
    qt_gui = _types.ModuleType("PyQt5.QtGui")
    qt_gui.QImage = mock.MagicMock()
    pyqt5 = _types.ModuleType("PyQt5")
    pyqt5.QtCore = qt_core
    pyqt5.QtGui = qt_gui

    mp_vision = mock.MagicMock()
    mp_vision.RunningMode = mock.MagicMock()
    mp_vision.PoseLandmarkerOptions = mock.MagicMock()
    mp_vision.PoseLandmarker = mock.MagicMock()
    mp_python = _types.ModuleType("mediapipe.tasks.python")
    mp_python.vision = mp_vision
    mp_python.BaseOptions = mock.MagicMock()
    mp_tasks = _types.ModuleType("mediapipe.tasks")
    mp_tasks.python = mp_python
    mp = _types.ModuleType("mediapipe")
    mp.tasks = mp_tasks
    mp.Image = mock.MagicMock()
    mp.ImageFormat = mock.MagicMock()

    cv2_stub = mock.MagicMock()

    sys.modules.update(
        {
            "PyQt5": pyqt5,
            "PyQt5.QtCore": qt_core,
            "PyQt5.QtGui": qt_gui,
            "mediapipe": mp,
            "mediapipe.tasks": mp_tasks,
            "mediapipe.tasks.python": mp_python,
            "mediapipe.tasks.python.vision": mp_vision,
            "cv2": cv2_stub,
        }
    )


_install_ui_worker_stubs()

import ui_worker  # noqa: E402


class WorkerStreamOwnershipTests(unittest.TestCase):
    def test_current_capture_including_replacement_released_on_stream_exit(self):
        worker = ui_worker.CameraWorker(0)
        worker._running = True

        old_cap = mock.Mock()
        old_cap.read.return_value = (False, None)  # first read fails → reconnect
        new_cap = mock.Mock()
        landmarker = mock.MagicMock()
        landmarker.detect_for_video.return_value.pose_landmarks = []
        emitted: list[str] = []

        frame = mock.Mock()
        frame.shape = (480, 640, 3)
        frame.tobytes.return_value = b"\x00" * (480 * 640 * 3)

        def new_cap_read():
            # First frame after reconnect succeeds; then the loop should exit.
            worker._running = False
            return True, frame

        new_cap.read.side_effect = new_cap_read

        with mock.patch.object(
            ui_worker.config, "READ_FAILURE_RECONNECT_THRESHOLD", 1
        ), mock.patch.object(
            ui_worker.config, "RECONNECT_MAX_ATTEMPTS", 5
        ), mock.patch.object(
            ui_worker, "open_camera", return_value=new_cap
        ), mock.patch.object(
            ui_worker, "interruptible_sleep", return_value=True
        ), mock.patch.object(
            ui_worker.cv2, "flip", side_effect=lambda f, axis: f
        ), mock.patch.object(
            ui_worker.cv2, "cvtColor", side_effect=lambda f, code: f
        ):
            worker._stream_loop(
                old_cap, landmarker, ui_worker.MonotonicClock(),
                lambda s: emitted.append(s) or True,
            )

        # Original capture was released when replaced during reconnect.
        old_cap.release.assert_called_once()
        # The replacement (current) capture is released when the stream exits.
        new_cap.release.assert_called_once()
        # Reopen success alone must NOT report TRACKING.
        self.assertNotIn("TRACKING", emitted)
        self.assertIn("RECONNECTING", emitted)
        self.assertIn("CONNECTING", emitted)


class ExplanationWorkerRunTests(unittest.TestCase):
    """ExplanationWorker emits its result/finished signals on a (template) run."""

    def test_success_run_emits_result(self):
        from ui_worker import ExplanationWorker

        worker = object.__new__(ExplanationWorker)  # QThread stub has no __init__
        worker._evidence = {}
        worker._force = False
        worker.result_ready = mock.MagicMock()
        worker.finished_ok = mock.MagicMock()
        worker.run()  # run() directly exercises the same path
        worker.result_ready.emit.assert_called_once()
        worker.finished_ok.emit.assert_called_once_with(True)


if __name__ == "__main__":
    unittest.main()
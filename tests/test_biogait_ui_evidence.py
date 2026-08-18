"""
Regression tests for the live UI evidence semantics (items 12, 13, 14 / 24 P-Q-R).

No camera, GUI display, or MediaPipe download: heavy modules (cv2, mediapipe,
PyQt5) are stubbed and the CameraWorker is exercised structurally (object
constructed via __new__) so `_emit_evidence()` can be driven with a fake
signal emitter. The tests verify:

- P: a current NO_POSE frame does NOT display stale prior knee values;
- Q: rolling PO availability from the retained window still works;
- R: rolling ROM payload keys use explicit rolling_* names (never whole-session
  ROM and never bare `left_knee_rom_deg`).
"""
from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BIOGAIT = REPO / "biogait"
sys.path.insert(0, str(BIOGAIT))


def _install_stubs():
    sys.modules.setdefault(
        "cv2",
        types.SimpleNamespace(
            CAP_PROP_FPS=5,
            VideoCapture=object,
            cvtColor=lambda img, code: img,
            COLOR_BGR2RGB=0,
            flip=lambda frame, d: frame,
        ),
    )
    sys.modules.setdefault("PyQt5", types.SimpleNamespace())
    sys.modules.setdefault(
        "PyQt5.QtCore",
        types.SimpleNamespace(QObject=object, pyqtSignal=lambda *a, **k: None),
    )
    sys.modules.setdefault("PyQt5.QtGui", types.SimpleNamespace(QImage=object))
    sys.modules.setdefault("mediapipe", types.SimpleNamespace())
    sys.modules.setdefault("mediapipe.tasks", types.SimpleNamespace())
    sys.modules.setdefault("mediapipe.tasks.python", types.SimpleNamespace())
    sys.modules.setdefault("mediapipe.tasks.python.vision", types.SimpleNamespace())


_install_stubs()

from evidence_features import build_frame_evidence  # noqa: E402
from session_analysis import SessionAccumulator  # noqa: E402
from ui_worker import CameraWorker  # noqa: E402


def _lm(x, y, z, visibility=1.0):
    return {"x": x, "y": y, "z": z, "visibility": visibility}


def _scene():
    return {
        "left_shoulder": _lm(0.0, 1.5, 0.0),
        "right_shoulder": _lm(0.3, 1.5, 0.0),
        "left_wrist": _lm(0.0, 1.4, 0.2),
        "right_wrist": _lm(0.3, 1.4, 0.2),
        "left_hip": _lm(0.0, 1.0, 0.0),
        "right_hip": _lm(0.3, 1.0, 0.0),
        "left_knee": _lm(0.0, 0.5, 0.0),
        "right_knee": _lm(0.3, 0.5, 0.0),
        "left_ankle": _lm(0.0, 0.0, 0.0),
        "right_ankle": _lm(0.3, 0.0, 0.0),
    }


def _make_worker():
    worker = object.__new__(CameraWorker)
    worker._evidence_acc = SessionAccumulator(max_frames=300)
    payloads: list[dict] = []
    worker.evidence_ready = types.SimpleNamespace(emit=payloads.append)
    return worker, payloads


def _add_available(worker, idx=0, timestamp=0.0):
    ev = build_frame_evidence(_scene(), idx, timestamp)
    worker._evidence_acc.add(ev.to_dict())


def _add_no_pose(worker, idx=1, timestamp=0.033):
    ev = build_frame_evidence({}, idx, timestamp)
    worker._evidence_acc.add(ev.to_dict())


class CurrentVsRollingTests(unittest.TestCase):
    def test_no_pose_current_frame_does_not_show_stale_values(self):
        worker, payloads = _make_worker()
        _add_available(worker, 0, 0.0)
        _add_no_pose(worker, 1, 0.033)
        worker._emit_evidence()
        payload = payloads[-1]
        # Current state is the LATEST processed frame (no pose) => None, not
        # the older available frame's angles.
        self.assertIsNone(payload["left_knee_sagittal_deg"])
        self.assertIsNone(payload["right_knee_sagittal_deg"])
        self.assertIs(payload["available"], False)
        self.assertIs(payload["quality"].get("available"), False)

    def test_available_current_frame_shows_values(self):
        worker, payloads = _make_worker()
        _add_available(worker, 0, 0.0)
        worker._emit_evidence()
        payload = payloads[-1]
        self.assertIs(payload["available"], True)
        self.assertIsNotNone(payload["left_knee_sagittal_deg"])
        self.assertIsNotNone(payload["right_knee_sagittal_deg"])

    def test_rolling_availability_still_reported(self):
        worker, payloads = _make_worker()
        _add_available(worker, 0, 0.0)
        _add_no_pose(worker, 1, 0.033)
        _add_available(worker, 2, 0.066)
        _add_no_pose(worker, 3, 0.099)
        worker._emit_evidence()
        payload = payloads[-1]
        self.assertAlmostEqual(payload["rolling_po_availability_rate"], 0.5)
        # Rolling rate is independent of current-frame availability.
        self.assertIs(payload["available"], False)

    def test_rolling_rom_payload_keys_and_no_session_names(self):
        worker, payloads = _make_worker()
        for i in range(3):
            _add_available(worker, i, i * 0.033)
        worker._emit_evidence()
        payload = payloads[-1]
        self.assertIn("rolling_left_knee_rom_deg", payload)
        self.assertIn("rolling_right_knee_rom_deg", payload)
        self.assertNotIn("left_knee_rom_deg", payload)
        self.assertNotIn("right_knee_rom_deg", payload)
        self.assertIsNotNone(payload["rolling_left_knee_rom_deg"])

    def test_empty_window_emits_safe_defaults(self):
        worker, payloads = _make_worker()
        worker._emit_evidence()
        payload = payloads[-1]
        self.assertIsNone(payload["left_knee_sagittal_deg"])
        self.assertIs(payload["available"], False)
        self.assertIsNone(payload["rolling_po_availability_rate"])


if __name__ == "__main__":
    unittest.main()
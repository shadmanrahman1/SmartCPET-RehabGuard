"""
Tests for biogait/evidence_schema.py and session_controller.py (Sprint C C1/C2).
No Qt / camera / network required.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "biogait"))

from evidence_schema import (  # noqa: E402
    SCHEMA_VERSION,
    SchemaValidationError,
    session_header,
    validate_evidence_record,
)
from session_controller import (  # noqa: E402
    BioGaitSessionController,
    ST_IDLE,
    ST_RUNNING,
    ST_STOPPED,
)


class EvidenceSchemaTests(unittest.TestCase):
    def test_session_header_valid(self):
        hdr = session_header(data_origin="REAL_VIDEO_MEDIAPIPE", processing_mode="offline_mediapipe_video")
        self.assertEqual(hdr["schema_version"], SCHEMA_VERSION)
        self.assertEqual(hdr["module"], "biogait")
        self.assertEqual(hdr["data_origin"], "REAL_VIDEO_MEDIAPIPE")
        self.assertEqual(hdr["processing_mode"], "offline_mediapipe_video")

    def test_invalid_data_origin_rejected(self):
        with self.assertRaises(SchemaValidationError):
            session_header(data_origin="MADE_UP", processing_mode="live_mediapipe")

    def test_invalid_processing_mode_rejected(self):
        with self.assertRaises(SchemaValidationError):
            session_header(data_origin="SYNTHETIC_FIXTURE", processing_mode="weird")

    def test_nan_rejected(self):
        with self.assertRaises(SchemaValidationError):
            validate_evidence_record({"left_knee_sagittal_deg": float("nan")})
        with self.assertRaises(SchemaValidationError):
            validate_evidence_record({"value": float("inf")})

    def test_forbidden_identity_key_rejected(self):
        with self.assertRaises(SchemaValidationError):
            validate_evidence_record({"metadata": {"patient_name": "x"}})

    def test_none_value_allowed(self):
        validate_evidence_record({"left_knee_sagittal_deg": None})  # no raise

    def test_invalid_provenance_enum_rejected(self):
        with self.assertRaises(SchemaValidationError):
            validate_evidence_record({"classification": "NOT_A_PROV"})
        validate_evidence_record({"classification": "REFERENCE_DERIVED"})


class SessionControllerTests(unittest.TestCase):
    def test_state_lifecycle(self):
        ctrl = BioGaitSessionController()
        self.assertEqual(ctrl.state, ST_IDLE)
        ctrl.start()
        self.assertEqual(ctrl.state, ST_RUNNING)
        ctrl.stop()
        self.assertEqual(ctrl.state, ST_STOPPED)

    def test_receive_only_when_running(self):
        ctrl = BioGaitSessionController()
        with self.assertRaises(ValueError):
            ctrl.receive_frame_evidence({"schema_version": "1.0"})
        ctrl.start()
        ctrl.receive_frame_evidence(_fake_evidence())
        self.assertEqual(ctrl.processed_frames, 1)

    def test_reset_returns_to_idle(self):
        ctrl = BioGaitSessionController()
        ctrl.start()
        ctrl.receive_frame_evidence(_fake_evidence())
        ctrl.reset()
        self.assertEqual(ctrl.state, ST_IDLE)
        self.assertEqual(ctrl.processed_frames, 0)

    def test_export_research_session_privacy_and_label(self):
        ctrl = BioGaitSessionController()
        ctrl.start()
        ctrl.receive_frame_evidence(_fake_evidence())
        export = ctrl.export_research_session()
        self.assertEqual(export["data_origin"], "REAL_VIDEO_MEDIAPIPE")
        self.assertEqual(export["processing_mode"], "live_mediapipe")
        self.assertNotIn("session_label", export)
        # No raw camera/path/person fields leaked.
        text = _safe(export)
        for banned in ("camera", ".mp4", "C:", "participant", "patient_name"):
            self.assertNotIn(banned, text)

    def test_export_session_label_only_when_supplied(self):
        ctrl = BioGaitSessionController()
        ctrl.start()
        export = ctrl.export_research_session(session_label="demo_01")
        self.assertEqual(export.get("session_label"), "demo_01")


class SessionTimingTests(unittest.TestCase):
    def test_elapsed_freezes_after_stop(self):
        from unittest import mock as _mock
        ctrl = BioGaitSessionController()
        with _mock.patch("time.monotonic", side_effect=[100.0, 150.0]):
            ctrl.start()
            ctrl.stop()
        self.assertEqual(ctrl._start_mono, 100.0)
        self.assertEqual(ctrl._stop_mono, 150.0)
        # STOPPED elapsed is frozen to stop-start regardless of now.
        self.assertAlmostEqual(ctrl.elapsed_seconds, 50.0)
        with _mock.patch("time.monotonic", side_effect=[10**9]):
            self.assertAlmostEqual(ctrl.elapsed_seconds, 50.0)

    def test_stop_in_idle_is_noop(self):
        ctrl = BioGaitSessionController()
        ctrl.stop()
        self.assertEqual(ctrl.state, ST_IDLE)
        self.assertIsNone(ctrl.elapsed_seconds)


class SessionExportScopeTests(unittest.TestCase):
    def _ev(self, i):
        return {
            "schema_version": "1.0", "exercise": "kimore_ex5_squat", "frame_index": i,
            "timestamp_seconds": float(i) / 30.0,
            "quality": {"available": True, "left_po_available": True, "right_po_available": True},
            "primary_outcomes": {"left_knee_sagittal_deg": 150.0, "right_knee_sagittal_deg": 148.0},
            "control_factors": {},
        }

    def test_full_export_exceeds_300(self):
        ctrl = BioGaitSessionController()
        ctrl.start()
        for i in range(350):
            ctrl.receive_frame_evidence(self._ev(i))
        full = ctrl.export_research_session(export_scope="full")
        self.assertEqual(full["exported_frame_count"], 350)
        self.assertEqual(full["processed_frames"], 350)
        self.assertEqual(len(full["aligned_arrays"]["timestamps_s"]), 350)
        self.assertFalse(full["session_truncated"])

    def test_rolling_export_bounded_at_300(self):
        ctrl = BioGaitSessionController()
        ctrl.start()
        for i in range(350):
            ctrl.receive_frame_evidence(self._ev(i))
        rolling = ctrl.export_research_session(export_scope="rolling")
        self.assertEqual(rolling["exported_frame_count"], 300)
        self.assertEqual(len(rolling["aligned_arrays"]["timestamps_s"]), 300)

    def test_explicit_limit_marks_truncation(self):
        ctrl = BioGaitSessionController(max_session_frames=5)
        ctrl.start()
        for i in range(10):
            ctrl.receive_frame_evidence(self._ev(i))
        full = ctrl.export_research_session(export_scope="full")
        self.assertTrue(full["session_truncated"])
        self.assertEqual(full["session_frame_limit"], 5)
        self.assertEqual(full["exported_frame_count"], 5)


class SessionThreadSafetyTests(unittest.TestCase):
    def test_concurrent_receive_and_export_safe(self):
        import threading
        ctrl = BioGaitSessionController(max_session_frames=500)
        ctrl.start()
        errors = []

        def _writer():
            try:
                for i in range(200):
                    ctrl.receive_frame_evidence({
                        "schema_version": "1.0", "exercise": "kimore_ex5_squat", "frame_index": i,
                        "timestamp_seconds": float(i) / 30.0,
                        "quality": {"available": True, "left_po_available": True, "right_po_available": True},
                        "primary_outcomes": {"left_knee_sagittal_deg": 150.0, "right_knee_sagittal_deg": 148.0},
                        "control_factors": {},
                    })
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        t = threading.Thread(target=_writer)
        t.start()
        exported = None
        for _ in range(50):
            exported = ctrl.export_research_session(export_scope="full")
        t.join()
        self.assertEqual(errors, [])
        self.assertEqual(exported["processed_frames"], 200)


def _fake_evidence():
    return {
        "schema_version": "1.0",
        "exercise": "kimore_ex5_squat",
        "frame_index": 0,
        "timestamp_seconds": 0.0,
        "quality": {"available": True, "left_po_available": True, "right_po_available": True},
        "primary_outcomes": {"left_knee_sagittal_deg": 150.0, "right_knee_sagittal_deg": 148.0},
        "control_factors": {},
    }


def _safe(obj):
    import json
    return json.dumps(obj)


if __name__ == "__main__":
    unittest.main()

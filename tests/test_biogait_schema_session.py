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

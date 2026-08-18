"""
Tests for the versioned research-session export schema (Phase I / M4).

Uses synthetic FrameEvidence dicts; no camera/GUI/network. Verifies
structure, JSON round-tripping, and the no-PII guard.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "biogait"))

from evidence_features import build_frame_evidence  # noqa: E402
from session_analysis import (  # noqa: E402
    SESSION_SCHEMA_VERSION,
    build_session_export,
    descriptive_temporal_features,
)


def _lm(x, y, z, visibility=1.0):
    return {"x": x, "y": y, "z": z, "visibility": visibility}


def _default_landmarks():
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


def _frames(n=3):
    frames = []
    for i in range(n):
        frames.append(
            build_frame_evidence(
                _default_landmarks(), i, i * 0.033
            ).to_dict()
        )
    return frames


def _source():
    return {
        "input_source": "demo_video.mp4",
        "video_fps_hz": 30.0,
        "fps_used_hz": 30.0,
        "frames_read": 3,
        "fps_trusted_from_video": True,
    }


def _provenance():
    return {"primary_outcomes": {"classification": "ENGINEERING_ADAPTED"}}


def _quality():
    return {
        "frames_added": 3,
        "available_frames": 3,
        "unavailable_frames": 0,
        "availability_rate": 1.0,
        "evicted_frames": 0,
    }


def _descriptors():
    arrays = {
        "timestamps_s": [0.0, 0.033, 0.066],
        "left_knee_sagittal_deg": [100.0, 101.0, 103.0],
        "right_knee_sagittal_deg": [99.0, 100.0, 102.0],
    }
    return descriptive_temporal_features(arrays)


def _reference():
    return {"left": {"warning": None}, "right": {"warning": None}}


class SessionExportTests(unittest.TestCase):
    def test_top_level_structure(self):
        export = build_session_export(
            source=_source(),
            method_provenance=_provenance(),
            quality_summary=_quality(),
            frames=_frames(),
            session_descriptors=_descriptors(),
            kimore_reference_analysis=_reference(),
            limitations=["limitation A"],
        )
        self.assertEqual(export["schema_version"], SESSION_SCHEMA_VERSION)
        self.assertEqual(export["module"], "biogait")
        self.assertEqual(export["exercise"], "kimore_ex5_squat")
        expected = {
            "schema_version", "module", "exercise", "source",
            "method_provenance", "quality_summary", "frames",
            "session_descriptors", "kimore_reference_analysis", "limitations",
        }
        self.assertEqual(set(export), expected)

    def test_frames_preserved_and_ordered(self):
        export = build_session_export(
            source=_source(), method_provenance=_provenance(),
            quality_summary=_quality(), frames=_frames(),
            session_descriptors=_descriptors(),
            kimore_reference_analysis=_reference(), limitations=[],
        )
        self.assertEqual(
            [f["frame_index"] for f in export["frames"]], [0, 1, 2]
        )
        self.assertIsNotNone(export["frames"][0]["primary_outcomes"]["left_knee_sagittal_deg"])

    def test_frames_can_be_excluded(self):
        export = build_session_export(
            source=_source(), method_provenance=_provenance(),
            quality_summary=_quality(), frames=_frames(),
            session_descriptors=_descriptors(),
            kimore_reference_analysis=_reference(), limitations=[],
            include_frames=False,
        )
        self.assertEqual(export["frames"], [])

    def test_json_roundtrip(self):
        export = build_session_export(
            source=_source(), method_provenance=_provenance(),
            quality_summary=_quality(), frames=_frames(),
            session_descriptors=_descriptors(),
            kimore_reference_analysis=_reference(), limitations=["x"],
        )
        text = json.dumps(export)
        loaded = json.loads(text)
        self.assertEqual(loaded["schema_version"], SESSION_SCHEMA_VERSION)
        self.assertEqual(len(loaded["frames"]), 3)

    def test_limitations_are_present_and_strings(self):
        export = build_session_export(
            source=_source(), method_provenance=_provenance(),
            quality_summary=_quality(), frames=_frames(),
            session_descriptors=_descriptors(),
            kimore_reference_analysis=_reference(),
            limitations=["a", "b"],
        )
        self.assertEqual(export["limitations"], ["a", "b"])

    def test_no_pii_guard_triggers_on_sensitive_source(self):
        bad_source = dict(_source())
        bad_source["input_source"] = "subject_name_scan.mp4"
        with self.assertRaises(AssertionError):
            build_session_export(
                source=bad_source, method_provenance=_provenance(),
                quality_summary=_quality(), frames=_frames(),
                session_descriptors=_descriptors(),
                kimore_reference_analysis=_reference(), limitations=[],
            )

    def test_imported_schema_is_public(self):
        import session_analysis  # noqa: F401
        self.assertTrue(hasattr(session_analysis, "build_session_export"))


if __name__ == "__main__":
    unittest.main()
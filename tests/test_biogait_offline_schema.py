"""
Tests for the versioned research-session export schema (Phase I / M4) with
strict JSON / data-safety behavior (items 16, 23).

Uses synthetic FrameEvidence dicts; no camera/GUI/network. Verifies structure,
JSON round-tripping, allow_nan=False, forbidden-key rejection, and the neutral
source metadata that never persists a local input path.
"""
from __future__ import annotations

import json
import math
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
    return [
        build_frame_evidence(_default_landmarks(), i, i * 0.033).to_dict()
        for i in range(n)
    ]


def _source():
    # Neutral source metadata — the local/absolute input path is NEVER
    # persisted in the research JSON.
    return {
        "source_type": "local_video",
        "timing_model": "constant_frame_rate_from_fps",
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


def _temporal():
    def _side(warning):
        return {
            "warning": warning,
            "filtered_signal": [] if warning else [1.0, 2.0, 3.0],
            "maxima_indices": [] if warning else [0, 2],
            "candidate_repetition_durations_s": [] if warning else [1.0],
        }

    return {
        "reference": {
            "classification": "REFERENCE_DERIVED",
            "offline": True,
            "left": _side(None),
            "right": _side(None),
            "summary": {
                "left_maxima_count": 2,
                "right_maxima_count": 2,
                "left_candidate_durations_s": [1.0],
                "right_candidate_durations_s": [1.0],
                "bilateral_pairing_status": "deferred",
            },
        },
        "adapted": {
            "classification": "ENGINEERING_ADAPTED",
            "offline": True,
            "left": _side("missing_samples_require_resampling"),
            "right": _side("missing_samples_require_resampling"),
            "summary": {
                "left_maxima_count": 0,
                "right_maxima_count": 0,
                "left_candidate_durations_s": [],
                "right_candidate_durations_s": [],
                "bilateral_pairing_status": "deferred",
            },
        },
    }


class SessionSchemaTests(unittest.TestCase):
    def test_top_level_structure(self):
        export = build_session_export(
            source=_source(), method_provenance=_provenance(),
            quality_summary=_quality(), frames=_frames(),
            session_descriptors=_descriptors(),
            temporal_analysis=_temporal(), limitations=["limitation A"],
        )
        self.assertEqual(export["schema_version"], SESSION_SCHEMA_VERSION)
        self.assertEqual(export["module"], "biogait")
        self.assertEqual(export["exercise"], "kimore_ex5_squat")
        expected = {
            "schema_version", "module", "exercise", "source",
            "method_provenance", "quality_summary", "frames",
            "session_descriptors", "temporal_analysis", "limitations",
        }
        self.assertEqual(set(export), expected)
        self.assertNotIn("kimore_reference_analysis", export)

    def test_frames_preserved_and_ordered(self):
        export = build_session_export(
            source=_source(), method_provenance=_provenance(),
            quality_summary=_quality(), frames=_frames(),
            session_descriptors=_descriptors(),
            temporal_analysis=_temporal(), limitations=[],
        )
        self.assertEqual([f["frame_index"] for f in export["frames"]], [0, 1, 2])

    def test_frames_can_be_excluded(self):
        export = build_session_export(
            source=_source(), method_provenance=_provenance(),
            quality_summary=_quality(), frames=_frames(),
            session_descriptors=_descriptors(),
            temporal_analysis=_temporal(), limitations=[],
            include_frames=False,
        )
        self.assertEqual(export["frames"], [])

    def test_temporal_analysis_provenance_branches(self):
        export = build_session_export(
            source=_source(), method_provenance=_provenance(),
            quality_summary=_quality(), frames=_frames(),
            session_descriptors=_descriptors(),
            temporal_analysis=_temporal(), limitations=[],
        )
        ta = export["temporal_analysis"]
        self.assertEqual(ta["reference"]["classification"], "REFERENCE_DERIVED")
        self.assertEqual(ta["adapted"]["classification"], "ENGINEERING_ADAPTED")
        self.assertNotIn("left_reference_maxima_count", ta["adapted"]["summary"])

    def test_no_nan_or_inf_json_allowed(self):
        export = build_session_export(
            source=_source(), method_provenance=_provenance(),
            quality_summary=_quality(), frames=_frames(),
            session_descriptors=_descriptors(),
            temporal_analysis=_temporal(), limitations=[],
        )
        # allow_nan=False must not be needed because no NaN exists.
        text = json.dumps(export, allow_nan=False)
        loaded = json.loads(text)
        self.assertEqual(loaded["schema_version"], SESSION_SCHEMA_VERSION)

    def test_nan_in_export_value_raises_on_serialize(self):
        # FrameEvidence never emits NaN, but the serializer must refuse it.
        frames = _frames()
        frames[0]["primary_outcomes"]["left_knee_sagittal_deg"] = float("nan")
        export = build_session_export(
            source=_source(), method_provenance=_provenance(),
            quality_summary=_quality(), frames=frames,
            session_descriptors=_descriptors(),
            temporal_analysis=_temporal(), limitations=[],
        )
        with self.assertRaises(ValueError):
            json.dumps(export, allow_nan=False)

    def test_constant_frame_rate_timing_model_metadata(self):
        export = build_session_export(
            source=_source(), method_provenance=_provenance(),
            quality_summary=_quality(), frames=_frames(),
            session_descriptors=_descriptors(),
            temporal_analysis=_temporal(), limitations=[],
        )
        self.assertEqual(
            export["source"]["timing_model"], "constant_frame_rate_from_fps"
        )

    def test_local_input_path_is_never_persisted(self):
        export = build_session_export(
            source=_source(), method_provenance=_provenance(),
            quality_summary=_quality(), frames=_frames(),
            session_descriptors=_descriptors(),
            temporal_analysis=_temporal(), limitations=[],
        )
        text = json.dumps(export)
        self.assertEqual(export["source"]["source_type"], "local_video")
        self.assertNotIn("input_source", export["source"])
        for leaked in ("C:\\", "/Users/", "demo_video.mp4", "patients/"):
            self.assertNotIn(leaked, text)

    def test_forbidden_key_deep_raises_value_error(self):
        source = _source()
        source["research_meta"] = {"owner": {"participant_id": 7}}
        with self.assertRaises(ValueError):
            build_session_export(
                source=source, method_provenance=_provenance(),
                quality_summary=_quality(), frames=_frames(),
                session_descriptors=_descriptors(),
                temporal_analysis=_temporal(), limitations=[],
            )

    def test_forbidden_patient_key_raises_value_error(self):
        source = _source()
        source["patient"] = "id"
        with self.assertRaises(ValueError):
            build_session_export(
                source=source, method_provenance=_provenance(),
                quality_summary=_quality(), frames=_frames(),
                session_descriptors=_descriptors(),
                temporal_analysis=_temporal(), limitations=[],
            )

    def test_benign_scientific_text_containing_name_does_not_fail(self):
        frames = _frames()
        frames[0]["quality"]["landmark_name"] = "left_hip"
        frames[0]["metadata"]["note"] = "the anatomical landmark name is stored verbatim"
        export = build_session_export(
            source=_source(), method_provenance=_provenance(),
            quality_summary=_quality(), frames=frames,
            session_descriptors=_descriptors(),
            temporal_analysis=_temporal(), limitations=["ok"],
        )
        self.assertEqual(len(export["frames"]), 3)

    def test_forbidden_check_is_not_assert(self):
        source = _source()
        source["subject_id"] = 1
        with self.assertRaises(ValueError):
            build_session_export(
                source=source, method_provenance=_provenance(),
                quality_summary=_quality(), frames=_frames(),
                session_descriptors=_descriptors(),
                temporal_analysis=_temporal(), limitations=[],
            )

    def test_all_export_numbers_finite_recursively(self):
        def check(obj):
            if isinstance(obj, float) or isinstance(obj, int):
                value = float(obj)
                self.assertTrue(math.isfinite(value), f"non-finite {value}")
            elif isinstance(obj, dict):
                for v in obj.values():
                    check(v)
            elif isinstance(obj, list):
                for v in obj:
                    check(v)

        export = build_session_export(
            source=_source(), method_provenance=_provenance(),
            quality_summary=_quality(), frames=_frames(),
            session_descriptors=_descriptors(),
            temporal_analysis=_temporal(), limitations=[],
        )
        check(export)


if __name__ == "__main__":
    unittest.main()
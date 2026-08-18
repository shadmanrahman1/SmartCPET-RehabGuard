"""
Tests for biogait/session_analysis.py — bounded accumulator, aligned arrays,
descriptive features, and the versioned session export schema.

Synthetic deterministic data only. No camera/GUI/network. Descriptive
features are tested as kinematic math, not as clinical scores.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "biogait"))

import config  # noqa: E402

from evidence_features import build_frame_evidence  # noqa: E402
from session_analysis import (  # noqa: E402
    FORBIDDEN_EXPORT_KEYS,
    SESSION_SCHEMA_VERSION,
    SELECTED_CONTROL_FACTOR_STREAMS,
    SessionAccumulator,
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


def _evidence(frame_index, timestamp_s, available=True, left=None, right=None):
    scene = _default_landmarks() if available else {}
    ev = build_frame_evidence(scene, frame_index, timestamp_s)
    if left is not None:
        ev.primary_outcomes["left_knee_sagittal_deg"] = left
    if right is not None:
        ev.primary_outcomes["right_knee_sagittal_deg"] = right
    return ev.to_dict()


class AccumulatorTests(unittest.TestCase):
    def test_counts_available_and_unavailable(self):
        acc = SessionAccumulator()
        acc.add(_evidence(0, 0.0))
        acc.add(_evidence(1, 0.033, available=False))
        acc.add(_evidence(2, 0.066))
        self.assertEqual(acc.total_added, 3)
        self.assertEqual(acc.available_count, 2)
        self.assertEqual(acc.unavailable_count, 1)

    def test_bounded_window_evicts_oldest(self):
        acc = SessionAccumulator(max_frames=5)
        for i in range(10):
            acc.add(_evidence(i, i * 0.033))
        self.assertEqual(acc.retained_frames, 5)
        self.assertEqual(acc.evicted_count, 5)
        self.assertEqual(acc.total_added, 10)
        self.assertEqual(acc.frames()[0]["frame_index"], 5)

    def test_add_validates_required_keys(self):
        acc = SessionAccumulator()
        with self.assertRaises(ValueError):
            acc.add({"frame_index": 0})

    def test_aligned_arrays_preserve_every_frame_and_none(self):
        acc = SessionAccumulator()
        acc.add(_evidence(0, 0.0, available=False))
        ev1 = _evidence(1, 0.033, left=120.0, right=118.0)
        ev1["primary_outcomes"]["left_knee_sagittal_deg"] = None
        acc.add(ev1)
        acc.add(_evidence(2, 0.066, left=130.0, right=128.0))
        aligned = acc.aligned_arrays()
        self.assertEqual(aligned["timestamps_s"], [0.0, 0.033, 0.066])
        self.assertEqual(aligned["left_knee_sagittal_deg"], [None, None, 130.0])
        self.assertEqual(aligned["right_knee_sagittal_deg"], [None, 118.0, 128.0])
        self.assertEqual(len(aligned["torso_area_m2"]), 3)
        self.assertIsNone(aligned["torso_area_m2"][0])

    def test_retained_window_counters_separate_from_lifetime(self):
        acc = SessionAccumulator(max_frames=4)
        for i in range(6):
            acc.add(_evidence(i, i * 0.1, available=(i % 2 == 0)))
        self.assertEqual(acc.total_added, 6)
        self.assertEqual(acc.available_count, 3)
        self.assertEqual(acc.unavailable_count, 3)
        self.assertEqual(acc.retained_frames, 4)
        self.assertEqual(acc.retained_available_count, 2)
        self.assertEqual(acc.retained_unavailable_count, 2)
        self.assertAlmostEqual(acc.retained_availability_rate, 0.5)

    def test_control_factor_streams_renamed(self):
        acc = SessionAccumulator()
        acc.add(_evidence(0, 0.0))
        arrays = acc.aligned_arrays()
        self.assertIn("knee_euclidean_3d_m", arrays)
        self.assertIn("knee_delta_y_m", arrays)
        self.assertNotIn("knee_distance_m", arrays)
        for name in SELECTED_CONTROL_FACTOR_STREAMS:
            self.assertIn(name, arrays)

    def test_effective_sample_rate_from_timestamps(self):
        acc = SessionAccumulator()
        for i in range(10):
            acc.add(_evidence(i, i / 30.0))
        self.assertAlmostEqual(acc.effective_sample_rate(), 30.0, places=0)

    def test_effective_sample_rate_none_when_single(self):
        acc = SessionAccumulator()
        acc.add(_evidence(0, 0.0))
        self.assertIsNone(acc.effective_sample_rate())


class DescriptiveFeaturesTests(unittest.TestCase):
    def test_session_duration_and_rom(self):
        arrays = {
            "timestamps_s": [0.0, 1.0, 2.0, 3.0],
            "left_knee_sagittal_deg": [100.0, 120.0, 140.0, 130.0],
            "right_knee_sagittal_deg": [90.0, 110.0, 130.0, 120.0],
        }
        desc = descriptive_temporal_features(arrays)
        self.assertEqual(desc["session_duration_s"], 3.0)
        self.assertAlmostEqual(desc["left_knee_rom_deg"], 40.0)
        self.assertAlmostEqual(desc["right_knee_rom_deg"], 40.0)
        self.assertAlmostEqual(desc["left_right_rom_difference_deg"], 0.0)

    def test_angular_velocity_peak_and_mean(self):
        arrays = {
            "timestamps_s": [0.0, 1.0, 2.0],
            "left_knee_sagittal_deg": [100.0, 110.0, 130.0],
            "right_knee_sagittal_deg": [100.0, 120.0, 100.0],
        }
        desc = descriptive_temporal_features(arrays)
        self.assertAlmostEqual(desc["left_peak_abs_angular_velocity_deg_s"], 20.0)
        self.assertAlmostEqual(desc["left_mean_abs_angular_velocity_deg_s"], 15.0)
        self.assertAlmostEqual(desc["right_peak_abs_angular_velocity_deg_s"], 20.0)
        self.assertAlmostEqual(desc["right_mean_abs_angular_velocity_deg_s"], 20.0)

    def test_angular_velocity_skips_gaps_index_aligned(self):
        arrays = {
            "timestamps_s": [0.0, 1.0, 2.0, 3.0],
            "left_knee_sagittal_deg": [100.0, 130.0, None, 100.0],
            "right_knee_sagittal_deg": [100.0, 100.0, None, 130.0],
        }
        desc = descriptive_temporal_features(arrays)
        self.assertEqual(desc["left_angular_velocity_deg_s"], [30.0])
        self.assertEqual(desc["right_angular_velocity_deg_s"], [0.0])

    def test_no_event_count_fields_in_descriptors(self):
        arrays = {
            "timestamps_s": [0.0, 1.0],
            "left_knee_sagittal_deg": [100.0, 120.0],
            "right_knee_sagittal_deg": [100.0, 120.0],
        }
        desc = descriptive_temporal_features(arrays)
        for banned in ("maxima", "candidate", "repetition", "deferred", "pairing"):
            self.assertFalse(any(banned in k for k in desc), desc)
        for banned in ("risk", "pass", "score", "clinical"):
            self.assertFalse(any(banned in k for k in desc))

    def test_insufficient_data_yields_none(self):
        arrays = {
            "timestamps_s": [0.0],
            "left_knee_sagittal_deg": [100.0],
            "right_knee_sagittal_deg": [100.0],
        }
        desc = descriptive_temporal_features(arrays)
        self.assertIsNone(desc["session_duration_s"])
        self.assertIsNone(desc["left_knee_rom_deg"])


class SessionExportTests(unittest.TestCase):
    def _source(self):
        return {
            "source_type": "local_video",
            "timing_model": "constant_frame_rate_from_fps",
            "video_fps_hz": 30.0,
            "fps_used_hz": 30.0,
            "frames_read": 3,
            "fps_trusted_from_video": True,
        }

    def _frames(self):
        return [build_frame_evidence(_default_landmarks(), i, i * 0.033).to_dict() for i in range(3)]

    def _descriptors(self):
        return {
            "session_duration_s": 0.066,
            "effective_sample_rate_hz": 30.0,
            "left_knee_rom_deg": 3.0,
            "right_knee_rom_deg": 3.0,
        }

    def _temporal(self):
        return {
            "reference": {
                "classification": "REFERENCE_DERIVED",
                "offline": True,
                "left": {"warning": None, "maxima_indices": [0, 2]},
                "right": {"warning": None, "maxima_indices": [0, 2]},
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
                "left": {"warning": "missing_samples_require_resampling"},
                "right": {"warning": "missing_samples_require_resampling"},
                "summary": {
                    "left_maxima_count": 0,
                    "right_maxima_count": 0,
                    "left_candidate_durations_s": [],
                    "right_candidate_durations_s": [],
                    "bilateral_pairing_status": "deferred",
                },
            },
        }

    def _export(self, **overrides):
        kwargs = dict(
            source=self._source(),
            method_provenance={"primary_outcomes": {"classification": "ENGINEERING_ADAPTED"}},
            quality_summary={"frames_added": 3, "available_frames": 3, "unavailable_frames": 0, "availability_rate": 1.0, "evicted_frames": 0},
            frames=self._frames(),
            session_descriptors=self._descriptors(),
            temporal_analysis=self._temporal(),
            limitations=["limitation A"],
        )
        kwargs.update(overrides)
        return build_session_export(**kwargs)

    def test_top_level_uses_temporal_analysis(self):
        export = self._export()
        self.assertEqual(export["schema_version"], SESSION_SCHEMA_VERSION)
        self.assertNotIn("kimore_reference_analysis", export)
        self.assertIn("temporal_analysis", export)
        expected = {
            "schema_version", "module", "exercise", "source",
            "method_provenance", "quality_summary", "frames",
            "session_descriptors", "temporal_analysis", "limitations",
        }
        self.assertEqual(set(export), expected)

    def test_temporal_analysis_branches_have_classification(self):
        export = self._export()
        ta = export["temporal_analysis"]
        self.assertEqual(ta["reference"]["classification"], "REFERENCE_DERIVED")
        self.assertEqual(ta["adapted"]["classification"], "ENGINEERING_ADAPTED")
        self.assertEqual(ta["reference"]["summary"]["bilateral_pairing_status"], "deferred")

    def test_json_roundtrip_no_nan(self):
        export = self._export()
        text = json.dumps(export, allow_nan=False)
        loaded = json.loads(text)
        self.assertEqual(loaded["schema_version"], SESSION_SCHEMA_VERSION)

    def test_local_path_never_persisted(self):
        export = self._export()
        text = json.dumps(export)
        self.assertEqual(export["source"]["source_type"], "local_video")
        self.assertIn("timing_model", export["source"])
        for leaked in ("C:\\", "/Users/", "demo_video.mp4", "patients/"):
            self.assertNotIn(leaked, text)

    def test_forbidden_keys_raise_value_error(self):
        for key in ("patient_id", "participant_id", "subject_id", "email"):
            frames = self._frames()
            frames[0]["metadata"][key] = "x"
            with self.assertRaises(ValueError):
                self._export(frames=frames)

    def test_forbidden_key_in_source_nested_raises(self):
        source = self._source()
        source["meta"] = {"owner": {"subject_name": "id"}}
        with self.assertRaises(ValueError):
            self._export(source=source)

    def test_benign_text_containing_name_does_not_fail(self):
        frames = self._frames()
        frames[0]["quality"]["landmark_name"] = "left_hip"
        frames[0]["metadata"]["note"] = "the anatomical landmark name is stored verbatim"
        export = self._export(frames=frames)
        self.assertEqual(len(export["frames"]), 3)

    def test_forbidden_set_contains_identity_keys(self):
        self.assertTrue({"patient_id", "participant_id", "subject_id", "email"}
                        <= FORBIDDEN_EXPORT_KEYS)


if __name__ == "__main__":
    unittest.main()
"""
Tests for biogait/session_analysis.py — bounded accumulator, effective sample
rate, descriptive features.

Synthetic deterministic data only. No camera/GUI/network. Descriptive
features are tested as kinematic math, not as clinical scores.
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "biogait"))

from evidence_features import build_frame_evidence  # noqa: E402
from session_analysis import (  # noqa: E402
    SELECTED_CONTROL_FACTOR_STREAMS,
    SessionAccumulator,
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
    ev = build_frame_evidence(
        scene, frame_index, timestamp_s, visibility_threshold=0.55
    )
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
        self.assertEqual(acc.retained_frames, 3)

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

    def test_finite_arrays_exclude_unavailable_frames(self):
        acc = SessionAccumulator()
        acc.add(_evidence(0, 0.0, available=False))
        acc.add(_evidence(1, 0.033, left=120.0, right=118.0))
        acc.add(_evidence(2, 0.066, left=130.0, right=128.0))
        arrays = acc.finite_arrays()
        self.assertEqual(arrays["timestamps_s"], [0.033, 0.066])
        self.assertEqual(arrays["left_knee_sagittal_deg"], [120.0, 130.0])
        self.assertFalse(any(v is None for v in arrays["timestamps_s"]))

    def test_finite_arrays_include_selected_cf_streams(self):
        acc = SessionAccumulator()
        acc.add(_evidence(0, 0.0))
        arrays = acc.finite_arrays()
        for name in SELECTED_CONTROL_FACTOR_STREAMS:
            self.assertIn(name, arrays)
        self.assertIsNotNone(arrays["torso_area_m2"][0])

    def test_effective_sample_rate_from_timestamps(self):
        acc = SessionAccumulator()
        for i in range(10):
            acc.add(_evidence(i, i / 30.0))
        rate = acc.effective_sample_rate()
        self.assertIsNotNone(rate)
        self.assertAlmostEqual(rate, 30.0, places=0)

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
        # deltas: L -> [10, 20]; R -> [20, -20]
        self.assertAlmostEqual(desc["left_peak_abs_angular_velocity_deg_s"], 20.0)
        self.assertAlmostEqual(desc["left_mean_abs_angular_velocity_deg_s"], 15.0)
        self.assertAlmostEqual(desc["right_peak_abs_angular_velocity_deg_s"], 20.0)
        self.assertAlmostEqual(desc["right_mean_abs_angular_velocity_deg_s"], 20.0)

    def test_insufficient_data_yields_none(self):
        arrays = {
            "timestamps_s": [0.0],
            "left_knee_sagittal_deg": [100.0],
            "right_knee_sagittal_deg": [100.0],
        }
        desc = descriptive_temporal_features(arrays)
        self.assertIsNone(desc["session_duration_s"])
        self.assertIsNone(desc["left_knee_rom_deg"])
        self.assertIsNone(desc["effective_sample_rate_hz"])

    def test_reference_summary_features(self):
        arrays = {
            "timestamps_s": [0.0, 2.0, 4.0],
            "left_knee_sagittal_deg": [100.0, 140.0, 100.0],
            "right_knee_sagittal_deg": [100.0, 140.0, 100.0],
        }
        summary = {
            "n_reference_event_candidates": 3,
            "candidate_repetition_durations_s": [2.0, 2.0],
        }
        desc = descriptive_temporal_features(arrays, reference_summary=summary)
        self.assertEqual(desc["n_reference_event_candidates"], 3)
        self.assertEqual(desc["candidate_repetition_durations_s"], [2.0, 2.0])

    def test_no_clinical_fields_emitted(self):
        arrays = {
            "timestamps_s": [0.0, 1.0],
            "left_knee_sagittal_deg": [100.0, 120.0],
            "right_knee_sagittal_deg": [100.0, 120.0],
        }
        desc = descriptive_temporal_features(arrays)
        for banned in ("risk", "pass", "score", "clinical"):
            self.assertFalse(any(banned in k for k in desc))


if __name__ == "__main__":
    unittest.main()
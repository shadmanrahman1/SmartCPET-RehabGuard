"""
Tests for biogait/reference_temporal.py — offline source-aligned KIMORE
reference path and the ACTUAL-fps ENGINEERING_ADAPTED path.

Synthetic deterministic signals only. These tests verify the reference
analysis mechanics and provenance boundaries, NOT clinical validity.
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "biogait"))

from reference_temporal import (  # noqa: E402
    KIMORE_FIRST_RETAINED_MATLAB_SAMPLE,
    KIMORE_INITIAL_DISCARDED_SAMPLES,
    KIMORE_REFERENCE_FS_HZ,
    KIMORE_WRAP_DIFF_THRESHOLD_DEG,
    detect_maxima,
    detect_minima,
    kimore_adapted_ex5_temporal_analysis,
    kimore_reference_ex5_temporal_analysis,
    kimore_reference_sign_flip_correction,
    remove_initial_samples,
    side_event_summary,
    validate_timestamps,
)


FS = 30.0


def _periodic_knee_stream(seconds=20.0, cycles_per_second=0.5):
    """Bilateral-style periodic knee flexion (no wrap) at 30 Hz."""
    n = int(FS * seconds)
    stream = []
    for i in range(n):
        t = i / FS
        angle = 170.0 + 45.0 * math.sin(2 * math.pi * cycles_per_second * t)
        stream.append(angle)
    return stream


def _timestamps(n, fs=FS):
    return [i / fs for i in range(n)]


class TrimTests(unittest.TestCase):
    def test_matlab_10_to_end_semantics_by_default(self):
        seq = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
        self.assertEqual(remove_initial_samples(seq), [10, 11, 12])

    def test_offsets_constants(self):
        self.assertEqual(KIMORE_INITIAL_DISCARDED_SAMPLES, 9)
        self.assertEqual(KIMORE_FIRST_RETAINED_MATLAB_SAMPLE, 10)

    def test_zero_based_and_matlab_mapping_explicit(self):
        seq = list(range(1, 13))
        trimmed = remove_initial_samples(seq)
        self.assertEqual(trimmed[0], 10)
        self.assertEqual(seq[KIMORE_INITIAL_DISCARDED_SAMPLES], trimmed[0])


class SignFlipCorrectionTests(unittest.TestCase):
    def test_sign_flip_negates_on_large_positive_diff(self):
        corrected, count = kimore_reference_sign_flip_correction([0, 10, 350, 0])
        self.assertEqual(count, 2)
        self.assertEqual(corrected[2], -350.0)

    def test_sign_flip_negates_on_large_negative_diff(self):
        corrected, count = kimore_reference_sign_flip_correction([0, -350])
        self.assertEqual(count, 1)
        self.assertEqual(corrected[1], 350.0)

    def test_not_360_unwrap(self):
        corrected, _ = kimore_reference_sign_flip_correction([0, 10, 350])
        self.assertEqual(corrected[2], -350.0)
        corrected2, _ = kimore_reference_sign_flip_correction([0, -350])
        self.assertEqual(corrected2[1], 350.0)

    def test_no_correction_for_small_diffs(self):
        corrected, count = kimore_reference_sign_flip_correction([100, 102, 99, 105])
        self.assertEqual(count, 0)

    def test_corrections_use_previously_corrected_values(self):
        corrected, count = kimore_reference_sign_flip_correction([10, 350, 5])
        self.assertEqual(count, 2)
        self.assertEqual(corrected[2], -5.0)

    def test_threshold_constant_defined(self):
        self.assertEqual(KIMORE_WRAP_DIFF_THRESHOLD_DEG, 100.0)
        self.assertEqual(KIMORE_REFERENCE_FS_HZ, 30.0)


class ExtremaTests(unittest.TestCase):
    def test_maxima_and_minima_on_clean_sine(self):
        n = 600
        signal = [170 + 45 * math.sin(2 * math.pi * 0.5 * i / FS) for i in range(n)]
        maxima, _ = detect_maxima(signal, distance=6)
        minima, _ = detect_minima(signal, distance=6)
        self.assertGreater(len(maxima), 0)
        self.assertEqual(len(maxima), len(minima))


class RateGateTests(unittest.TestCase):
    """Reference path gates on the resolved fps (items 1 / 24 A/B)."""

    def test_29_97_source_reference_warns_adapted_runs(self):
        stream = _periodic_knee_stream()
        ref = kimore_reference_ex5_temporal_analysis(stream, fs=29.97)
        self.assertEqual(ref["warning"], "reference_requires_30hz_or_resampling")
        self.assertEqual(ref["classification"], "REFERENCE_DERIVED")
        self.assertEqual(ref["filtered_signal"], [])
        adapted = kimore_adapted_ex5_temporal_analysis(stream, fs=29.97)
        self.assertEqual(adapted["classification"], "ENGINEERING_ADAPTED")
        self.assertIsNone(adapted["warning"])
        self.assertGreater(len(adapted["filtered_signal"]), 0)
        self.assertEqual(adapted["fs_hz"], 29.97)

    def test_25_hz_source_reference_warns_adapted_runs(self):
        stream = _periodic_knee_stream()
        ref = kimore_reference_ex5_temporal_analysis(stream, fs=25.0)
        self.assertEqual(ref["warning"], "reference_requires_30hz_or_resampling")
        adapted = kimore_adapted_ex5_temporal_analysis(stream, fs=25.0)
        self.assertEqual(adapted["classification"], "ENGINEERING_ADAPTED")
        self.assertIsNone(adapted["warning"])

    def test_60_hz_source_reference_warns_adapted_runs(self):
        stream = _periodic_knee_stream()
        ref = kimore_reference_ex5_temporal_analysis(stream, fs=60.0)
        self.assertEqual(ref["warning"], "reference_requires_30hz_or_resampling")
        adapted = kimore_adapted_ex5_temporal_analysis(stream, fs=60.0)
        self.assertEqual(adapted["classification"], "ENGINEERING_ADAPTED")

    def test_30_hz_source_reference_allowed(self):
        stream = _periodic_knee_stream()
        ref = kimore_reference_ex5_temporal_analysis(stream, fs=30.0)
        self.assertIsNone(ref["warning"])
        self.assertEqual(ref["classification"], "REFERENCE_DERIVED")
        self.assertGreater(len(ref["filtered_signal"]), 0)

    def test_tiny_float_noise_around_30_ok(self):
        stream = _periodic_knee_stream()
        ref = kimore_reference_ex5_temporal_analysis(stream, fs=30.0 + 1e-9)
        self.assertIsNone(ref["warning"])


class MissingSampleTests(unittest.TestCase):
    def test_missing_samples_reference_warn_no_filtering(self):
        stream = _periodic_knee_stream()
        gap = [stream[0], None, stream[2]] + stream[3:]
        ref = kimore_reference_ex5_temporal_analysis(gap, fs=30.0)
        self.assertEqual(ref["warning"], "missing_samples_require_resampling")
        self.assertEqual(ref["filtered_signal"], [])

    def test_missing_samples_adapted_warn_no_filtering(self):
        stream = _periodic_knee_stream()
        gap = [stream[0], None, stream[2]] + stream[3:]
        adapted = kimore_adapted_ex5_temporal_analysis(gap, fs=25.0)
        self.assertEqual(adapted["warning"], "missing_samples_require_resampling")
        self.assertEqual(adapted["filtered_signal"], [])


class TimestampValidationTests(unittest.TestCase):
    """Timestamp integrity (items 5 / 24 F/G/H)."""

    def test_validate_timestamps_rejects_length_mismatch(self):
        ok, issue = validate_timestamps([0.0, 0.1], 3, uniform_at=30.0)
        self.assertFalse(ok)
        self.assertIn("timestamp count", issue)

    def test_validate_timestamps_rejects_non_monotonic(self):
        ok, issue = validate_timestamps([0.0, 0.033, 0.033], 3, uniform_at=30.0)
        self.assertFalse(ok)
        self.assertIn("strictly increasing", issue)

    def test_validate_timestamps_rejects_non_finite(self):
        ok, issue = validate_timestamps([0.0, float("nan"), 0.1], 3, uniform_at=30.0)
        self.assertFalse(ok)

    def test_validate_timestamps_accepts_uniform_30hz(self):
        ok, issue = validate_timestamps([0.0, 1 / 30, 2 / 30], 3, uniform_at=30.0)
        self.assertTrue(ok)
        self.assertIsNone(issue)

    def test_reference_timestamp_length_mismatch_warned(self):
        stream = _periodic_knee_stream()
        bad_ts = _timestamps(len(stream) - 1)  # wrong length
        ref = kimore_reference_ex5_temporal_analysis(stream, timestamps=bad_ts, fs=30.0)
        self.assertTrue(ref["warning"].startswith("invalid_reference_timestamps"))
        self.assertEqual(ref["filtered_signal"], [])

    def test_reference_non_uniform_timestamps_warned(self):
        stream = _periodic_knee_stream()
        ts = _timestamps(len(stream))
        # Keep strictly increasing but make one interval non-uniform (0.05 s).
        ts[10] = ts[9] + 0.05
        ts[11] = ts[10] + 1 / 30
        ref = kimore_reference_ex5_temporal_analysis(stream, timestamps=ts, fs=30.0)
        self.assertEqual(
            ref["warning"], "reference_requires_uniform_30hz_timestamps_or_resampling"
        )
        self.assertEqual(ref["filtered_signal"], [])

    def test_reference_uniform_30hz_timestamps_ok(self):
        stream = _periodic_knee_stream()
        ref = kimore_reference_ex5_temporal_analysis(stream, timestamps=_timestamps(len(stream)), fs=30.0)
        self.assertIsNone(ref["warning"])

    def test_adapted_non_uniform_timestamps_warned(self):
        stream = _periodic_knee_stream()
        ts = _timestamps(len(stream), fs=25.0)
        # Keep strictly increasing but make only the FINAL interval non-uniform.
        ts[-1] = ts[-2] + 0.5
        adapted = kimore_adapted_ex5_temporal_analysis(stream, timestamps=ts, fs=25.0)
        self.assertEqual(adapted["warning"], "adapted_requires_uniform_sampling_or_resampling")
        self.assertEqual(adapted["filtered_signal"], [])


class PipelineTests(unittest.TestCase):
    def test_full_pipeline_finds_candidates(self):
        stream = _periodic_knee_stream()
        timestamps = _timestamps(len(stream))
        result = kimore_reference_ex5_temporal_analysis(stream, timestamps, fs=30.0)
        self.assertIsNone(result["warning"])
        self.assertEqual(
            len(result["filtered_signal"]),
            len(stream) - KIMORE_INITIAL_DISCARDED_SAMPLES,
        )
        self.assertEqual(result["n_initial_samples_removed"], 9)
        self.assertEqual(result["first_retained_matlab_sample"], 10)
        self.assertEqual(result["source_index_convention"], "zero_based_python_index")
        self.assertGreater(len(result["maxima_indices"]), 1)
        self.assertGreater(len(result["minima_indices"]), 1)
        for cand in result["event_candidates"]:
            self.assertEqual(
                cand["original_index"], cand["index"] + result["n_initial_samples_removed"]
            )
            self.assertGreaterEqual(cand["original_index"], KIMORE_INITIAL_DISCARDED_SAMPLES)

    def test_event_time_s_uses_original_source_timeline(self):
        # With explicit timestamps, event time_s must read the ORIGINAL source
        # index (i.e. timestamps[original_index]), not restart at zero.
        stream = _periodic_knee_stream(seconds=10.0)
        timestamps = _timestamps(len(stream))
        result = kimore_reference_ex5_temporal_analysis(stream, timestamps, fs=30.0)
        self.assertGreater(len(result["event_candidates"]), 0)
        first = result["event_candidates"][0]
        self.assertAlmostEqual(first["time_s"], timestamps[first["original_index"]])

    def test_event_time_s_fallback_includes_source_offset(self):
        # Without timestamps, time_s = original_index / fs (never restarted at 0).
        stream = _periodic_knee_stream(seconds=10.0)
        result = kimore_reference_ex5_temporal_analysis(stream, fs=30.0)
        self.assertGreater(len(result["event_candidates"]), 0)
        for cand in result["event_candidates"]:
            expected = cand["original_index"] / 30.0
            self.assertAlmostEqual(cand["time_s"], expected)
            self.assertAlmostEqual(
                cand["time_s"],
                (cand["index"] + KIMORE_INITIAL_DISCARDED_SAMPLES) / 30.0,
            )


class SideEventSummaryTests(unittest.TestCase):
    """Generic per-side summary; separate provenance assigned by caller."""

    def _analysis(self, maxima_indices, durations):
        return {
            "maxima_indices": maxima_indices,
            "candidate_repetition_durations_s": durations,
        }

    def test_per_side_counts_and_deferred_pairing(self):
        left = self._analysis([0, 2], [2.0])
        right = self._analysis([0, 2, 4], [2.0, 2.0])
        summary = side_event_summary(left, right)
        self.assertEqual(summary["left_maxima_count"], 2)
        self.assertEqual(summary["right_maxima_count"], 3)
        self.assertEqual(summary["left_candidate_durations_s"], [2.0])
        self.assertEqual(summary["right_candidate_durations_s"], [2.0, 2.0])
        self.assertEqual(summary["bilateral_pairing_status"], "deferred")

    def test_no_combined_count_and_no_reference_suffix(self):
        left = self._analysis([0, 2], [2.0])
        right = self._analysis([0, 2], [2.0])
        summary = side_event_summary(left, right)
        self.assertNotIn("n_reference_event_candidates", summary)
        for key in summary:
            self.assertFalse(key.endswith("_reference_maxima_count"))
            self.assertFalse(key.endswith("_candidate_repetition_durations_s"))

    def test_handles_missing_side(self):
        summary = side_event_summary(None, self._analysis([0, 1], [1.0]))
        self.assertEqual(summary["left_maxima_count"], 0)
        self.assertEqual(summary["right_maxima_count"], 2)
        self.assertEqual(summary["bilateral_pairing_status"], "deferred")


if __name__ == "__main__":
    unittest.main()
"""
Tests for biogait/reference_temporal.py — offline KIMORE Ex5 reference
temporal analysis (trim, exact sign-flip correction, filtering, extrema,
event candidates) plus the ACTUAL-fps ENGINEERING_ADAPTED adapted path.

Synthetic deterministic signals only. These tests verify the reference
analysis mechanics, NOT clinical validity of the detected events.
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


class TrimTests(unittest.TestCase):
    def test_removes_initial_samples(self):
        self.assertEqual(remove_initial_samples([1, 2, 3, 4, 5], n=2), [3, 4, 5])

    def test_empty_when_trim_consumes_all(self):
        self.assertEqual(remove_initial_samples([1, 2], n=5), [])

    def test_negative_n_returns_copy(self):
        self.assertEqual(remove_initial_samples([1, 2], n=-1), [1, 2])

    def test_matlab_10_to_end_semantics_by_default(self):
        # MATLAB 1-based angle(10:end) discards samples 1..9 -> keeps 10,11,12.
        seq = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
        self.assertEqual(remove_initial_samples(seq), [10, 11, 12])

    def test_matlab_offsets_constants(self):
        self.assertEqual(KIMORE_INITIAL_DISCARDED_SAMPLES, 9)
        self.assertEqual(KIMORE_FIRST_RETAINED_MATLAB_SAMPLE, 10)

    def test_zero_based_and_matlab_mapping_explicit(self):
        # trimmed index 0 -> original Python index 9 -> MATLAB sample 10.
        seq = list(range(1, 13))  # [1..12]
        trimmed = remove_initial_samples(seq)
        self.assertEqual(trimmed[0], 10)
        self.assertEqual(seq[KIMORE_INITIAL_DISCARDED_SAMPLES], trimmed[0])
        self.assertEqual(KIMORE_FIRST_RETAINED_MATLAB_SAMPLE, 10)


class SignFlipCorrectionTests(unittest.TestCase):
    """Exact reference sign-flip logic (FIX 2) — NOT a +/-360 unwrap."""

    def test_sign_flip_negates_on_large_positive_diff(self):
        corrected, count = kimore_reference_sign_flip_correction([0, 10, 350, 0])
        # 350-10=340>100 -> 350 becomes -350; then 0-(-350)=350>100 -> 0 -> -0.
        self.assertEqual(count, 2)
        self.assertEqual(corrected[0], 0)
        self.assertEqual(corrected[1], 10)
        self.assertEqual(corrected[2], -350.0)
        self.assertEqual(corrected[3], 0.0)

    def test_sign_flip_negates_on_large_negative_diff(self):
        corrected, count = kimore_reference_sign_flip_correction([0, -300, 200])
        # -300-0=-300<-100 -> -300 becomes +300; 200-300=-100 not <-100 (boundary).
        self.assertEqual(count, 1)
        self.assertEqual(corrected[0], 0)
        self.assertEqual(corrected[1], 300.0)
        self.assertEqual(corrected[2], 200.0)

    def test_not_360_unwrap_on_positive_crossing(self):
        # If this were a +360 unwrap, 350-10 would become 350 -> 10 (or 370).
        corrected, _ = kimore_reference_sign_flip_correction([0, 10, 350])
        self.assertEqual(corrected[2], -350.0)

    def test_not_360_unwrap_on_negative_crossing(self):
        # If this were a -360 unwrap, -350-0 would become -350 -> +10 (or -370).
        corrected, _ = kimore_reference_sign_flip_correction([0, -350])
        self.assertEqual(corrected[1], 350.0)

    def test_no_correction_for_small_diffs(self):
        corrected, count = kimore_reference_sign_flip_correction([100, 102, 99, 105])
        self.assertEqual(count, 0)
        self.assertEqual(corrected, [100, 102, 99, 105])

    def test_corrections_use_previously_corrected_values(self):
        # 350 -> -350 (uses corrected 10); then 5-(-350)=355>100 -> 5 -> -5.
        corrected, count = kimore_reference_sign_flip_correction([10, 350, 5])
        self.assertEqual(count, 2)
        self.assertEqual(corrected[2], -5.0)

    def test_boundary_100_is_not_flagged(self):
        corrected, count = kimore_reference_sign_flip_correction([0, 100])
        self.assertEqual(count, 0)
        self.assertEqual(corrected, [0.0, 100.0])

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
        self.assertGreater(len(minima), 0)
        self.assertEqual(len(maxima), len(minima))


class ExactReferenceAnalysisTests(unittest.TestCase):
    def test_insufficient_samples_after_trim_yields_warning(self):
        result = kimore_reference_ex5_temporal_analysis(
            [170.0, 172.0, 174.0, 176.0, 178.0], fs=FS
        )
        self.assertEqual(result["warning"], "insufficient_samples_after_trimming")
        self.assertEqual(result["maxima_indices"], [])
        self.assertEqual(result["classification"], "REFERENCE_DERIVED")

    def test_full_pipeline_finds_candidates(self):
        stream = _periodic_knee_stream()
        timestamps = [i / FS for i in range(len(stream))]
        result = kimore_reference_ex5_temporal_analysis(stream, timestamps, fs=FS)
        self.assertIsNone(result["warning"])
        self.assertGreaterEqual(result["n_sign_corrections"], 0)
        # MATLAB 10:end -> 9 samples discarded in zero-based Python.
        self.assertEqual(
            len(result["filtered_signal"]),
            len(stream) - KIMORE_INITIAL_DISCARDED_SAMPLES,
        )
        self.assertEqual(result["n_initial_samples_removed"], 9)
        maxima = result["maxima_indices"]
        minima = result["minima_indices"]
        self.assertGreater(len(maxima), 1)
        self.assertGreater(len(minima), 1)
        durations = result["candidate_repetition_durations_s"]
        self.assertGreater(len(durations), 0)
        for d in durations:
            self.assertGreater(d, 0.0)

    def test_events_are_candidates_not_pass_fail(self):
        stream = _periodic_knee_stream()
        result = kimore_reference_ex5_temporal_analysis(stream, fs=FS)
        self.assertEqual(result["classification"], "REFERENCE_DERIVED")
        self.assertTrue(result["offline"])
        for cand in result["event_candidates"]:
            self.assertIn(cand["type"], ("max", "min"))
            self.assertGreaterEqual(cand["index"], 0)

    def test_original_index_offset_reported(self):
        stream = _periodic_knee_stream(seconds=20.0)
        result = kimore_reference_ex5_temporal_analysis(stream, fs=FS)
        self.assertEqual(
            result["first_retained_matlab_sample"], KIMORE_FIRST_RETAINED_MATLAB_SAMPLE
        )
        self.assertEqual(
            result["source_index_convention"], "zero_based_python_index"
        )
        for cand in result["event_candidates"]:
            self.assertEqual(
                cand["original_index"], cand["index"] + result["n_initial_samples_removed"]
            )
            # Event source index is zero-based: trimmed index 0 -> Python 9.
            self.assertGreaterEqual(cand["original_index"], KIMORE_INITIAL_DISCARDED_SAMPLES)

    # ── missing samples / 30 Hz gating (FIX 4 / 5) ─────────────────────────
    def test_missing_samples_warning_no_filtering(self):
        stream = _periodic_knee_stream()
        gap = [stream[0], None, stream[2]] + stream[3:]
        result = kimore_reference_ex5_temporal_analysis(gap, fs=FS)
        self.assertEqual(result["warning"], "missing_samples_require_resampling")
        self.assertEqual(result["filtered_signal"], [])
        self.assertEqual(result["maxima_indices"], [])
        self.assertEqual(result["classification"], "REFERENCE_DERIVED")

    def test_exact_path_requires_30hz(self):
        stream = _periodic_knee_stream()
        for bad_fs in (25.0, 29.97, 60.0):
            result = kimore_reference_ex5_temporal_analysis(stream, fs=bad_fs)
            self.assertEqual(
                result["warning"], "reference_requires_30hz_or_resampling"
            )
            self.assertEqual(result["filtered_signal"], [])
            self.assertEqual(result["classification"], "REFERENCE_DERIVED")

    def test_exact_path_accepts_tiny_float_noise_around_30(self):
        stream = _periodic_knee_stream()
        result = kimore_reference_ex5_temporal_analysis(stream, fs=30.0 + 1e-9)
        self.assertIsNone(result["warning"])
        self.assertEqual(result["classification"], "REFERENCE_DERIVED")


class AdaptedAnalysisTests(unittest.TestCase):
    def test_adapted_path_present_and_engineering_adapted(self):
        stream = _periodic_knee_stream()
        result = kimore_adapted_ex5_temporal_analysis(stream, fs=25.0)
        self.assertEqual(result["classification"], "ENGINEERING_ADAPTED")
        self.assertTrue(result["offline"])
        self.assertGreater(len(result["filtered_signal"]), 0)
        self.assertIn("adapted_note", result)

    def test_adapted_path_missing_samples_warns(self):
        stream = _periodic_knee_stream()
        gap = [stream[0], None, stream[2]] + stream[3:]
        result = kimore_adapted_ex5_temporal_analysis(gap, fs=25.0)
        self.assertEqual(result["warning"], "missing_samples_require_resampling")
        self.assertEqual(result["filtered_signal"], [])

    def test_adapted_result_is_clearly_not_reference(self):
        stream = _periodic_knee_stream()
        ref = kimore_reference_ex5_temporal_analysis(stream, fs=30.0)
        adapted25 = kimore_adapted_ex5_temporal_analysis(stream, fs=25.0)
        self.assertEqual(ref["classification"], "REFERENCE_DERIVED")
        self.assertEqual(adapted25["classification"], "ENGINEERING_ADAPTED")
        self.assertNotEqual(ref["fs_hz"], adapted25["fs_hz"])


class SideEventSummaryTests(unittest.TestCase):
    """Per-side summary only; bilateral pairing deferred (FIX 6)."""

    def _analysis(self, maxima_indices, durations):
        return {
            "maxima_indices": maxima_indices,
            "candidate_repetition_durations_s": durations,
            "event_candidates": [
                {"index": i, "original_index": i, "time_s": i / FS, "type": "max"}
                for i in maxima_indices
            ],
        }

    def test_per_side_counts_and_deferred_pairing(self):
        left = self._analysis([0, 2, 4], [2.0, 2.0])
        right = self._analysis([0, 2], [2.0])
        summary = side_event_summary(left, right)
        self.assertEqual(summary["left_reference_maxima_count"], 3)
        self.assertEqual(summary["right_reference_maxima_count"], 2)
        self.assertEqual(summary["left_candidate_repetition_durations_s"], [2.0, 2.0])
        self.assertEqual(summary["right_candidate_repetition_durations_s"], [2.0])
        self.assertEqual(summary["bilateral_pairing_status"], "deferred")

    def test_no_unified_combined_count_key(self):
        left = self._analysis([0, 2], [2.0])
        right = self._analysis([0, 2], [2.0])
        summary = side_event_summary(left, right)
        self.assertNotIn("n_reference_event_candidates", summary)
        self.assertNotIn("candidate_repetition_durations_s", summary)

    def test_handles_missing_side(self):
        summary = side_event_summary(None, self._analysis([0, 1], [1.0]))
        self.assertEqual(summary["left_reference_maxima_count"], 0)
        self.assertEqual(summary["right_reference_maxima_count"], 2)
        self.assertEqual(summary["bilateral_pairing_status"], "deferred")


if __name__ == "__main__":
    unittest.main()
"""
Tests for biogait/reference_temporal.py — offline KIMORE Ex5 reference
temporal analysis (trim, sign correction, extrema, event candidates).

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
    KIMORE_WRAP_DIFF_THRESHOLD_DEG,
    detect_maxima,
    detect_minima,
    kimore_reference_ex5_temporal_analysis,
    kimore_wrap_correction,
    merge_side_events,
    remove_initial_samples,
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


class WrapCorrectionTests(unittest.TestCase):
    def test_sign_correction_applied_at_large_jump(self):
        corrected, count = kimore_wrap_correction([0, 10, 350, 0])
        self.assertEqual(count, 1)
        self.assertEqual(corrected[0], 0)
        self.assertEqual(corrected[1], 10)
        self.assertEqual(corrected[2], -10)
        self.assertEqual(corrected[3], 0)

    def test_no_correction_for_small_diffs(self):
        corrected, count = kimore_wrap_correction([100, 102, 99, 105])
        self.assertEqual(count, 0)
        self.assertEqual(corrected, [100, 102, 99, 105])

    def test_negative_wrap_corrected_upward(self):
        corrected, count = kimore_wrap_correction([10, 0, -350, -360])
        # 0 -> -350: diff -350 < -100 -> shift +360 -> +10
        # +10 -> -360: diff -370 < -100 -> shift +360 -> 0
        self.assertEqual(count, 2)
        self.assertEqual(corrected, [10, 0, 10, 0])


class ExtremaTests(unittest.TestCase):
    def test_maxima_and_minima_on_clean_sine(self):
        n = 600
        signal = [170 + 45 * math.sin(2 * math.pi * 0.5 * i / FS) for i in range(n)]
        maxima, _ = detect_maxima(signal, distance=6)
        minima, _ = detect_minima(signal, distance=6)
        self.assertGreater(len(maxima), 0)
        self.assertGreater(len(minima), 0)
        self.assertEqual(len(maxima), len(minima))


class ReferenceAnalysisTests(unittest.TestCase):
    def test_insufficient_samples_after_trim_yields_warning(self):
        result = kimore_reference_ex5_temporal_analysis(
            [170.0, 172.0, 174.0, 176.0, 178.0], fs=FS
        )
        self.assertEqual(result["warning"], "insufficient_samples_after_trimming")
        self.assertEqual(result["maxima_indices"], [])

    def test_full_pipeline_finds_candidates(self):
        stream = _periodic_knee_stream()
        timestamps = [i / FS for i in range(len(stream))]
        result = kimore_reference_ex5_temporal_analysis(stream, timestamps, fs=FS)
        self.assertIsNone(result["warning"])
        self.assertGreaterEqual(result["n_sign_corrections"], 0)
        self.assertEqual(len(result["filtered_signal"]), len(stream) - 10)
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
        self.assertIn("classification", result)
        self.assertEqual(result["classification"], "REFERENCE_DERIVED")
        self.assertTrue(result["offline"])
        for cand in result["event_candidates"]:
            self.assertIn(cand["type"], ("max", "min"))
            self.assertGreaterEqual(cand["index"], 0)

    def test_original_index_offset_reported(self):
        stream = _periodic_knee_stream(seconds=20.0)
        result = kimore_reference_ex5_temporal_analysis(stream, fs=FS)
        for cand in result["event_candidates"]:
            self.assertEqual(
                cand["original_index"], cand["index"] + result["n_initial_samples_removed"]
            )


class MergeSideEventsTests(unittest.TestCase):
    def _analysis(self, max_counts):
        events = [
            {"index": i * 40, "original_index": i * 40 + 10,
             "time_s": i * 40 / FS, "type": "max"}
            for i in range(max_counts)
        ]
        return {"event_candidates": events}

    def test_merges_bilateral_maxima(self):
        summary = merge_side_events(self._analysis(2), self._analysis(3))
        self.assertEqual(summary["n_left_maxima"], 2)
        self.assertEqual(summary["n_right_maxima"], 3)
        self.assertEqual(summary["n_reference_event_candidates"], 5)
        self.assertGreater(len(summary["candidate_repetition_durations_s"]), 0)

    def test_handles_missing_side(self):
        summary = merge_side_events(None, self._analysis(2))
        self.assertEqual(summary["n_left_maxima"], 0)
        self.assertEqual(summary["n_reference_event_candidates"], 2)

    def test_durations_positive(self):
        summary = merge_side_events(self._analysis(3), None)
        for d in summary["candidate_repetition_durations_s"]:
            self.assertGreater(d, 0.0)


if __name__ == "__main__":
    unittest.main()
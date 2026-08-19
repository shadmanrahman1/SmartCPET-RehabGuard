"""
Tests for experiments/biogait/fps_sensitivity.py (B7, B20).
Synthetic deterministic angle sequences only; no clinical claims.
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "experiments" / "biogait"))

from fps_sensitivity import (  # noqa: E402
    DEFAULT_RATES,
    fps_sensitivity,
    resample_uniform,
)


def _periodic(seconds=20, cycles=5, base=170.0, amp=45.0):
    n = int(30 * seconds)
    return [base + amp * math.sin(2 * math.pi * cycles / seconds * i / 30) for i in range(n)]


class ResampleTests(unittest.TestCase):
    def test_resample_preserves_duration(self):
        src = _periodic()
        n_orig = len(src)
        duration = (n_orig - 1) / 30.0
        out = resample_uniform(src, 30.0, 25.0)
        expected = int(round(duration * 25.0)) + 1
        self.assertEqual(len(out), expected)

    def test_resample_deterministic(self):
        src = _periodic()
        a = resample_uniform(src, 30.0, 29.97)
        b = resample_uniform(src, 30.0, 29.97)
        self.assertEqual(a, b)


class FpsSensitivityTests(unittest.TestCase):
    def test_requires_30hz_source(self):
        with self.assertRaises(ValueError):
            fps_sensitivity([1.0] * 100, [1.0] * 100, src_fs=25.0)

    def test_anchor_extremes_are_roundtripped(self):
        stream = _periodic()
        result = fps_sensitivity(stream, stream, src_fs=30.0, rates=(25.0, 29.97, 60.0))
        left_rows = [r for r in result["rows"] if r["side"] == "left"]
        rates_present = sorted(r["fps"] for r in left_rows)
        self.assertIn(30.0, rates_present)
        self.assertIn(25.0, rates_present)
        self.assertIn(29.97, rates_present)
        self.assertIn(60.0, rates_present)

    def test_anchor_is_REFERENCE_DERIVED_others_adapted(self):
        stream = _periodic()
        result = fps_sensitivity(stream, stream, src_fs=30.0, rates=(15.0, 60.0))
        for r in result["rows"]:
            if r["fps"] == 30.0:
                self.assertEqual(r["classification"], "REFERENCE_DERIVED")
            else:
                self.assertEqual(r["classification"], "ENGINEERING_ADAPTED")

    def test_drift_keys_present_on_adapted_rates(self):
        stream = _periodic()
        result = fps_sensitivity(stream, stream, src_fs=30.0, rates=(25.0,))
        adapted = [r for r in result["rows"] if r["fps"] == 25.0][0]
        self.assertIn("rom_drift_abs", adapted["drift_vs_30hz"])
        self.assertIn("peak_angvel_drift_abs", adapted["drift_vs_30hz"])
        self.assertIn("event_count_diff", adapted["drift_vs_30hz"])
        self.assertIn("note", adapted)
        self.assertEqual(adapted["note"], "Engineering sensitivity experiment; not clinical accuracy.")

    def test_default_rates_include_spec_list(self):
        for r in (15, 20, 24, 25, 29.97, 30, 50, 60):
            self.assertIn(float(r), [round(x, 4) for x in DEFAULT_RATES])

    def test_data_origin_default_unknown(self):
        stream = _periodic()
        result = fps_sensitivity(stream, stream, src_fs=30.0, rates=(25.0,))
        self.assertEqual(result["data_origin"], "UNKNOWN_UNVALIDATED")

    def test_data_origin_propagates_to_result_and_rows(self):
        stream = _periodic()
        result = fps_sensitivity(stream, stream, src_fs=30.0, rates=(25.0,),
                                 data_origin="SYNTHETIC_FIXTURE")
        self.assertEqual(result["data_origin"], "SYNTHETIC_FIXTURE")
        for row in result["rows"]:
            self.assertEqual(row["data_origin"], "SYNTHETIC_FIXTURE")


if __name__ == "__main__":
    unittest.main()

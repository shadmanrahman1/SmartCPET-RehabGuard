"""
Tests for experiments/biogait/missingness_sensitivity.py (B8, B20).
Synthetic deterministic sequences only; no clinical claims.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "experiments" / "biogait"))

from kimore_adapter import synthetic_ex5_sequence  # noqa: E402
from missingness_sensitivity import (  # noqa: E402
    MISSINGNESS_LEVELS,
    missingness_sensitivity,
)


class MissingnessTests(unittest.TestCase):
    def test_zero_missingness_full_coverage(self):
        seq = synthetic_ex5_sequence(300, 30.0, seed=0)
        result = missingness_sensitivity(seq, levels=(0.0, 0.05), seed=0)
        zero = result["rows"][0]
        self.assertEqual(zero["missingness_level"], 0.0)
        self.assertEqual(zero["po_coverage"]["both"], 1.0)
        self.assertIn("runs", zero["reference_path_status"])

    def test_high_missingness_reduces_coverage_and_warns(self):
        seq = synthetic_ex5_sequence(300, 30.0, seed=0)
        result = missingness_sensitivity(seq, levels=(0.0, 0.30), seed=0)
        low = result["rows"][0]
        high = result["rows"][1]
        self.assertGreaterEqual(
            low["po_coverage"]["both"], high["po_coverage"]["both"]
        )
        self.assertNotEqual(high["po_coverage"]["both"], 1.0)
        self.assertIn("missing_samples_require_resampling", high["reference_path_status"])
        self.assertIn("missing_samples_require_resampling", high["adapted_path_status"])

    def test_rolling_availability_present(self):
        seq = synthetic_ex5_sequence(300, 30.0, seed=0)
        result = missingness_sensitivity(seq, levels=(0.0, 0.10), seed=0)
        for row in result["rows"]:
            self.assertIsNotNone(row["rolling_availability_rate"])

    def test_deterministic_with_seed(self):
        seq = synthetic_ex5_sequence(200, 30.0, seed=1)
        a = missingness_sensitivity(seq, levels=(0.1, 0.2), seed=42)
        b = missingness_sensitivity(seq, levels=(0.1, 0.2), seed=42)
        self.assertEqual(a["rows"], b["rows"])

    def test_burst_mode_flag(self):
        seq = synthetic_ex5_sequence(300, 30.0, seed=0)
        result = missingness_sensitivity(seq, levels=(0.2,), seed=0, burst=True)
        self.assertTrue(result["burst_dropout"])
        self.assertEqual(result["rows"][0]["missing_frames"], int(0.2 * 300))

    def test_levels_include_spec(self):
        self.assertEqual(MISSINGNESS_LEVELS, (0.0, 0.05, 0.10, 0.20, 0.30))

    def test_sampling_rate_required_when_unknown(self):
        seq = synthetic_ex5_sequence(200, 30.0, seed=0)
        seq["sampling_rate_hz"] = None
        result = missingness_sensitivity(seq, seed=0)
        self.assertEqual(result["status"], "sampling_rate_required")
        self.assertEqual(result["rows"], [])

    def test_data_origin_propagates(self):
        seq = synthetic_ex5_sequence(200, 30.0, seed=0)
        result = missingness_sensitivity(seq, seed=0, data_origin="SYNTHETIC_FIXTURE")
        self.assertEqual(result["data_origin"], "SYNTHETIC_FIXTURE")
        self.assertEqual(result["rows"][0]["data_origin"], "SYNTHETIC_FIXTURE")


if __name__ == "__main__":
    unittest.main()

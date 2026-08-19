"""
Tests for experiments/biogait/evaluate_kimore_ex5.py (B5, B20).
Synthetic sequences only; no clinical claims.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "experiments" / "biogait"))

from kimore_adapter import synthetic_ex5_sequence  # noqa: E402
from evaluate_kimore_ex5 import evaluate_sequence  # noqa: E402


class EvaluateKimoreTests(unittest.TestCase):
    def test_evaluate_synthetic_sequence(self):
        seq = synthetic_ex5_sequence(120, 30.0, seed=0)
        result = evaluate_sequence(seq)
        self.assertEqual(result["exercise"], "ex5_squat")
        self.assertEqual(result["n_frames"], 120)
        self.assertEqual(result["sampling_rate_hz"], 30.0)
        self.assertIsNotNone(result["po_coverage"]["left"])
        self.assertIsNotNone(result["po_coverage"]["right"])

    def test_neutral_keys_present_no_personal_ids(self):
        seq = synthetic_ex5_sequence(60, 30.0, seed=0)
        result = evaluate_sequence(seq)
        self.assertTrue(result["dataset_subject_key"])
        self.assertTrue(result["sequence_key"])
        for junk in ("participant", "name", "path", "video_file"):
            self.assertNotIn(junk, result)
            self.assertFalse(any(junk in k for k in result.keys()))

    def test_temporal_reference_and_adapted_branches(self):
        seq = synthetic_ex5_sequence(120, 30.0, seed=0)
        result = evaluate_sequence(seq)
        ta = result["temporal_analysis"]
        self.assertEqual(ta["reference"]["classification"], "REFERENCE_DERIVED")
        self.assertEqual(ta["adapted"]["classification"], "ENGINEERING_ADAPTED")
        self.assertIn("n_event_candidates", ta["reference"]["left"])
        self.assertIn("warning", ta["reference"]["left"])

    def test_no_clinical_fields(self):
        seq = synthetic_ex5_sequence(60, 30.0, seed=0)
        result = evaluate_sequence(seq)
        text = str(result).lower()
        for banned in ("diagnos", "clinical score", "correct", "incorrect", "cpo", "ccf", "cts"):
            self.assertNotIn(banned, text)


if __name__ == "__main__":
    unittest.main()

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


class EvaluatorContractTests(unittest.TestCase):
    """Items 5/6/8/9: no silent 30 Hz, timestamps, manifest, data_origin."""

    def _strip_fs(self, seq):
        seq = dict(seq)
        seq["sampling_rate_hz"] = None
        return seq

    def test_no_silent_30hz_fallback(self):
        seq = self._strip_fs(synthetic_ex5_sequence(60, 30.0, seed=0))
        result = evaluate_sequence(seq)  # no fs override
        self.assertEqual(result["sampling_rate_status"], "sampling_rate_required_for_temporal_analysis")
        self.assertIsNone(result["temporal_analysis"])
        self.assertIsNone(result["sampling_rate_hz"])

    def test_fs_override_unlocks_temporal(self):
        seq = self._strip_fs(synthetic_ex5_sequence(60, 30.0, seed=0))
        result = evaluate_sequence(seq, fs_override=25.0)
        self.assertEqual(result["sampling_rate_status"], "ok")
        self.assertIsNotNone(result["temporal_analysis"])
        self.assertEqual(result["sampling_rate_hz"], 25.0)

    def test_malformed_timestamps_reported_not_replaced(self):
        seq = synthetic_ex5_sequence(60, 30.0, seed=0)
        seq["timestamps_s"] = [float("nan")] * 60
        result = evaluate_sequence(seq)
        self.assertTrue(result["evaluation_status"].startswith("invalid_timestamps"))
        self.assertIsNone(result["temporal_analysis"])

    def test_data_origin_propagates(self):
        seq = synthetic_ex5_sequence(60, 30.0, seed=0)
        result = evaluate_sequence(seq, data_origin="SYNTHETIC_FIXTURE")
        self.assertEqual(result["data_origin"], "SYNTHETIC_FIXTURE")

    def test_metadata_only_manifest_rejected(self):
        import json
        import tempfile
        from pathlib import Path
        from evaluate_kimore_ex5 import main as eval_main

        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "m.json"
            manifest.write_text(json.dumps({"entries": [{"sequence_key": "k", "exercise": "ex5_squat"}]}), encoding="utf-8")
            code = eval_main(["--manifest", str(manifest)])
            self.assertNotEqual(code, 0)

    def test_parser_has_no_dataset_root_has_load(self):
        from evaluate_kimore_ex5 import _build_parser

        parser = _build_parser()
        names = {a.dest for a in parser._actions}
        self.assertNotIn("dataset_root", names)
        self.assertIn("load", names)
        self.assertIn("sequence_json", names)


if __name__ == "__main__":
    unittest.main()

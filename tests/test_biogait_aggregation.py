"""
Tests for experiments/biogait/aggregate_results.py (B12, integrity-corrected).

Verifies structure-based provenance extraction (never a whole-file tag), data
origin survival, and aggregator path privacy.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EXPERIMENTS = REPO / "experiments" / "biogait"
sys.path.insert(0, str(EXPERIMENTS))

from aggregate_results import aggregate, write_csv_tables  # noqa: E402
from common import atomic_json_write  # noqa: E402


def _eval_blob():
    """A session/evaluation-like blob with mixed method provenance."""
    return {
        "data_origin": "REAL_KIMORE_NATIVE_SKELETON",
        "temporal_analysis": {
            "reference": {"left": {"classification": "REFERENCE_DERIVED", "n_event_candidates": 2},
                          "right": {"classification": "REFERENCE_DERIVED", "n_event_candidates": 2}},
            "adapted": {"left": {"classification": "ENGINEERING_ADAPTED", "n_event_candidates": 3},
                        "right": {"classification": "ENGINEERING_ADAPTED", "n_event_candidates": 3}},
        },
        "descriptive": {"left_knee_rom_deg": 40.0, "right_knee_rom_deg": 38.0},
    }


def _fps_blob():
    """An fps_sensitivity blob with a 30-Hz reference anchor + adapted rows."""
    return {
        "data_origin": "SYNTHETIC_FIXTURE",
        "experiment": "fps_sensitivity",
        "rows": [
            {"side": "left", "fps": 30.0, "classification": "REFERENCE_DERIVED", "rom_deg": 90.0, "sampling": "anchor"},
            {"side": "left", "fps": 25.0, "classification": "ENGINEERING_ADAPTED", "rom_deg": 88.0,
             "drift_vs_30hz": {"rom_drift_abs": 2.0}},
        ],
    }


def _write(tmp, name, blob):
    p = Path(tmp) / name
    atomic_json_write(p, blob)
    return p


class AggregationTests(unittest.TestCase):
    def test_one_evaluation_yields_three_provenances(self):
        with tempfile.TemporaryDirectory() as tmp:
            inputs = {"evaluation": _write(tmp, "eval.json", _eval_blob())}
            agg = aggregate(inputs)
            per_prov = agg["per_provenance"]
            self.assertIn("REFERENCE_DERIVED", per_prov)
            self.assertIn("ENGINEERING_ADAPTED", per_prov)
            self.assertIn("DESCRIPTIVE", per_prov)

    def test_fps_rows_separated_by_classification(self):
        with tempfile.TemporaryDirectory() as tmp:
            inputs = {"fps_sensitivity": _write(tmp, "fps.json", _fps_blob())}
            agg = aggregate(inputs)
            ref = [r for r in agg["per_provenance"].get("REFERENCE_DERIVED", []) if r["key"].startswith("fps.30.0")]
            adapted = [r for r in agg["per_provenance"].get("ENGINEERING_ADAPTED", []) if r["key"].startswith("fps.25.0")]
            self.assertTrue(ref)
            self.assertTrue(adapted)
            # Drift metric stays under the adapted row's classification.
            drift = [r for r in agg["per_provenance"].get("ENGINEERING_ADAPTED", []) if "drift" in r["key"]]
            self.assertGreaterEqual(len(drift), 1)

    def test_data_origin_survives_aggregation(self):
        with tempfile.TemporaryDirectory() as tmp:
            inputs = {"evaluation": _write(tmp, "eval.json", _eval_blob())}
            agg = aggregate(inputs)
            for records in agg["per_provenance"].values():
                for r in records:
                    self.assertEqual(r["data_origin"], "REAL_KIMORE_NATIVE_SKELETON")

    def test_no_local_paths_persisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            inputs = {
                "evaluation": _write(tmp, "eval.json", _eval_blob()),
                "missing": Path(tmp) / "does_not_exist.json",
            }
            agg = aggregate(inputs)
            text = json.dumps(agg)
            self.assertIn("evaluation", agg["inputs_present"])
            self.assertIn("missing", agg["inputs_missing"])
            # No path/filename leak: label lists only.
            self.assertNotIn("eval.json", text)
            self.assertNotIn("does_not_exist.json", text)
            self.assertNotIn("C:", text)

    def test_inputs_are_label_lists(self):
        with tempfile.TemporaryDirectory() as tmp:
            inputs = {"a": _write(tmp, "a.json", _eval_blob())}
            agg = aggregate(inputs)
            self.assertIsInstance(agg["inputs_present"], list)
            self.assertEqual(agg["inputs_present"], ["a"])

    def test_csv_written_with_provenance_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            inputs = {"evaluation": _write(tmp, "eval.json", _eval_blob())}
            agg = aggregate(inputs)
            out = Path(tmp) / "out"
            write_csv_tables(agg, out)
            combined = (out / "aggregate_all.csv").read_text(encoding="utf-8")
            self.assertIn("method_provenance", combined)
            self.assertIn("data_origin", combined)


if __name__ == "__main__":
    unittest.main()

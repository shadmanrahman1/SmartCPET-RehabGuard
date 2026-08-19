"""
Tests for experiments/biogait/aggregate_results.py (B12, B20).
Verifies provenance separation and JSON/CSV outputs on small fixtures.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "experiments" / "biogait"))

from aggregate_results import (  # noqa: E402
    PROVENANCE_BY_INPUT,
    aggregate,
    write_csv_tables,
)


class AggregationTests(unittest.TestCase):
    def _write(self, tmp, name, blob):
        p = Path(tmp) / name
        p.write_text(json.dumps(blob), encoding="utf-8")
        return p

    def test_no_provenance_mixing(self):
        with tempfile.TemporaryDirectory() as tmp:
            inputs = {
                "reference": self._write(tmp, "ref.json", {"source_aligned": True}),
                "adapted": self._write(tmp, "ad.json", {"engineered": True}),
                "descriptive": self._write(tmp, "desc.json", {"rom": 12.0}),
            }
            agg = aggregate(inputs)
            for prov, records in agg["per_provenance"].items():
                for rec in records:
                    self.assertEqual(rec["provenance"], prov if prov != "UNCLASSIFIED" else "UNCLASSIFIED")

    def test_inputs_present_and_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            inputs = {
                "reference": self._write(tmp, "ref.json", {"a": 1}),
                "benchmark": Path(tmp) / "missing.json",
            }
            agg = aggregate(inputs)
            self.assertIn("reference", agg["inputs_present"])
            self.assertIn("benchmark", agg["inputs_missing"])
            self.assertGreaterEqual(agg["records_by_provenance"]["REFERENCE_DERIVED"], 1)

    def test_provenance_labels_map(self):
        self.assertEqual(PROVENANCE_BY_INPUT["reference"], "REFERENCE_DERIVED")
        self.assertEqual(PROVENANCE_BY_INPUT["adapted"], "ENGINEERING_ADAPTED")
        self.assertEqual(PROVENANCE_BY_INPUT["descriptive"], "DESCRIPTIVE")
        self.assertEqual(PROVENANCE_BY_INPUT["fps_sensitivity"], "ENGINEERING_ADAPTED")
        self.assertEqual(PROVENANCE_BY_INPUT["missingness"], "ENGINEERING_ADAPTED")
        self.assertEqual(PROVENANCE_BY_INPUT["benchmark"], "ENGINEERING_ADAPTED")

    def test_csv_has_provenance_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            inputs = {"reference": self._write(tmp, "ref.json", {"x": 1})}
            agg = aggregate(inputs)
            out = Path(tmp) / "out"
            write_csv_tables(agg, out)
            combined = (out / "aggregate_all.csv").read_text(encoding="utf-8")
            self.assertIn("provenance", combined)
            self.assertIn("REFERENCE_DERIVED", combined)


if __name__ == "__main__":
    unittest.main()

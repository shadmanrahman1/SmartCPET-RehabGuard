"""
Tests for experiments/biogait/make_paper_figures.py (B14, B20).
No matplotlib required (only the data-gated planner is exercised).
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "experiments" / "biogait"))

from make_paper_figures import plots_to_generate  # noqa: E402


class FigurePlanTests(unittest.TestCase):
    def test_pending_without_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            plans = plots_to_generate(Path(tmp))
            by_name = {p["figure"]: p for p in plans}
            self.assertEqual(by_name["A"]["status"], "PENDING_DATA")
            self.assertEqual(by_name["B"]["status"], "PENDING_DATA")
            self.assertEqual(by_name["C"]["status"], "PENDING_DATA")
            self.assertEqual(by_name["D"]["status"], "PENDING_DATA")

    def test_five_figures_planned(self):
        with tempfile.TemporaryDirectory() as tmp:
            plans = plots_to_generate(Path(tmp))
            self.assertEqual([p["figure"] for p in plans], ["A", "B", "C", "D", "E"])

    def test_fps_data_enables_figure_b(self):
        from common import atomic_json_write

        with tempfile.TemporaryDirectory() as tmp:
            atomic_json_write(Path(tmp) / "fps_sensitivity.json", {"rows": []})
            by_name = {p["figure"]: p for p in plots_to_generate(Path(tmp))}
            self.assertEqual(by_name["B"]["status"], "COMPLETE")


if __name__ == "__main__":
    unittest.main()

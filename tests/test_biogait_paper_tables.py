"""
Tests for experiments/biogait/make_paper_tables.py (B13, B20).
Verifies table structure and PENDING_DATA behavior without fabricated numbers.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "experiments" / "biogait"))

from make_paper_tables import (  # noqa: E402
    build_tables,
    render_markdown,
)
from common import atomic_json_write  # noqa: E402


class PaperTablesTests(unittest.TestCase):
    def test_static_tables_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            tables = build_tables(Path(tmp))
            self.assertIn("table1_components", tables)
            self.assertIn("table2_kimore_mapping", tables)
            self.assertIn("table3_protocol", tables)
            self.assertGreater(len(tables["table1_components"]["rows"]), 0)
            self.assertGreater(len(tables["table2_kimore_mapping"]["rows"]), 0)

    def test_table4_robustness_derived(self):
        with tempfile.TemporaryDirectory() as tmp:
            tables = build_tables(Path(tmp))
            rows = tables["table4_robustness"]["rows"]
            self.assertTrue(rows)
            self.assertIn("landmark_condition", tables["table4_robustness"]["headers"])

    def test_table5_pending_without_benchmark_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            tables = build_tables(Path(tmp))
            self.assertEqual(tables["table5_benchmark"]["status"], "PENDING_DATA")
            self.assertIn("PENDING", tables["table5_benchmark"]["rows"][0])

    def test_table6_pending_without_fps_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            tables = build_tables(Path(tmp))
            self.assertEqual(tables["table6_fps"]["status"], "PENDING_DATA")

    def test_table5_complete_when_benchmark_data_exists(self):
        bench = {
            "summary": {
                "REAL_VIDEO_BENCHMARK": "COMPLETE",
                "n_videos": 2, "n_success": 2,
                "aggregate": {
                    "total_frames": 1000,
                    "mean_ms_per_frame_over_videos": 12.0,
                    "p95_ms_per_frame_over_videos": 20.0,
                    "effective_throughput_fps_over_videos": 30.0,
                },
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            atomic_json_write(Path(tmp) / "benchmark_batch.json", bench)
            tables = build_tables(Path(tmp))
            self.assertEqual(tables["table5_benchmark"]["status"], "COMPLETE")

    def test_markdown_renders_all_tables(self):
        with tempfile.TemporaryDirectory() as tmp:
            tables = build_tables(Path(tmp))
            md = render_markdown(tables)
            for name in ("TABLE 1", "TABLE 2", "TABLE 3", "TABLE 4", "TABLE 5", "TABLE 6"):
                self.assertIn(name, md)


if __name__ == "__main__":
    unittest.main()

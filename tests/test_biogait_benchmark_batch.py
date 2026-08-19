"""
Tests for experiments/biogait/benchmark_batch.py (B11, B20).

Uses a mocked benchmark_video module to verify orchestration (per-video rows,
failure handling, PENDING summary when no real data). No camera/hardware.
"""
from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BIOGAIT = REPO / "biogait"
sys.path.insert(0, str(BIOGAIT))
sys.path.insert(0, str(REPO / "experiments" / "biogait"))

import benchmark_batch  # noqa: E402


class _FakeOK:
    def __init__(self):
        self.mean_ms_per_frame = 10.0
        self.median_ms_per_frame = 9.0
        self.p95_ms_per_frame = 15.0
        self.effective_throughput_fps = 30.0
        self.total_frames = 100
        self.world_landmark_availability_rate = 0.9


def _make_bv(results=None, raises=None):
    def _benchmark(video, out, fps):
        if raises is not None:
            raise raises
        return dict(
            mean_ms_per_frame=10.0,
            median_ms_per_frame=9.0,
            p95_ms_per_frame=15.0,
            effective_throughput_fps=30.0,
            total_frames=100,
            valid_pose_frames=80,
            world_landmark_available_frames=72,
            world_landmark_availability_rate=0.9,
            fps_used_hz=30.0,
            frame_width_px=1280,
            frame_height_px=720,
            data_origin="REAL_VIDEO_MEDIAPIPE",
        )

    return types.SimpleNamespace(benchmark=_benchmark)


class BenchmarkBatchTests(unittest.TestCase):
    def _patch_bv(self, bv):
        import sys as _s
        old = _s.modules.get("benchmark_video")
        _s.modules["benchmark_video"] = bv
        self.addCleanup(lambda: (_s.modules.__setitem__("benchmark_video", old) if old else _s.modules.pop("benchmark_video", None)))

    def test_pending_when_no_videos(self):
        import shutil
        import tempfile

        self._patch_bv(_make_bv())
        out = Path(tempfile.mkdtemp(prefix="bench_aggr_"))
        try:
            result = benchmark_batch.run_benchmark_batch(None, out)
        finally:
            shutil.rmtree(out, ignore_errors=True)
        self.assertEqual(result["summary"]["REAL_VIDEO_BENCHMARK"], "PENDING")
        self.assertEqual(result["n_videos_requested"], 0)

    def test_aggregate_pending_without_data(self):
        summary = benchmark_batch._aggregate([])
        self.assertEqual(summary["REAL_VIDEO_BENCHMARK"], "PENDING")

    def test_aggregate_complete_with_rows(self):
        row = {"status": "ok", "mean_ms_per_frame": 10.0, "median_ms_per_frame": 9.0,
               "p95_ms_per_frame": 15.0, "effective_throughput_fps": 30.0,
               "total_frames": 100, "valid_pose_frames": 80,
               "world_landmark_available_frames": 72,
               "world_landmark_availability_rate": 0.9}
        summary = benchmark_batch._aggregate([row])
        self.assertEqual(summary["REAL_VIDEO_BENCHMARK"], "COMPLETE")
        self.assertEqual(summary["aggregate"]["total_frames"], 100)
        # Weighted availability uses pooled counts, not a plain mean of rates.
        self.assertAlmostEqual(summary["aggregate"]["overall_world_landmark_availability_rate"], 0.9)
        self.assertAlmostEqual(summary["aggregate"]["macro_mean_world_landmark_availability_rate"], 0.9)
        # p95 is named as the mean of per-video p95s, never a "global p95".
        self.assertAlmostEqual(summary["aggregate"]["mean_of_video_p95_ms_per_frame"], 15.0)
        self.assertNotIn("p95_ms_per_frame_over_videos", summary["aggregate"])
        self.assertNotIn("global_p95", summary["aggregate"])

    def test_aggregate_weighted_availability_pooled(self):
        row_a = {"status": "ok", "mean_ms_per_frame": 1.0, "median_ms_per_frame": 1.0,
                 "p95_ms_per_frame": 2.0, "effective_throughput_fps": 30.0,
                 "total_frames": 10, "valid_pose_frames": 10,
                 "world_landmark_available_frames": 10,
                 "world_landmark_availability_rate": 1.0}
        row_b = {"status": "ok", "mean_ms_per_frame": 1.0, "median_ms_per_frame": 1.0,
                 "p95_ms_per_frame": 2.0, "effective_throughput_fps": 30.0,
                 "total_frames": 90, "valid_pose_frames": 90,
                 "world_landmark_available_frames": 45,
                 "world_landmark_availability_rate": 0.5}
        summary = benchmark_batch._aggregate([row_a, row_b])
        # Pooled = (10+45)/(10+90) = 0.55; macro mean of rates = (1.0+0.5)/2.
        self.assertAlmostEqual(
            summary["aggregate"]["overall_world_landmark_availability_rate"], 0.55
        )
        self.assertAlmostEqual(
            summary["aggregate"]["macro_mean_world_landmark_availability_rate"], 0.75
        )

    def test_privacy_no_filename_persisted(self):
        import json as _json
        import shutil
        import tempfile

        self._patch_bv(_make_bv())
        in_dir = Path(tempfile.mkdtemp(prefix="bench_priv_in_"))
        out_dir = Path(tempfile.mkdtemp(prefix="bench_priv_out_"))
        try:
            (in_dir / "Patient_Alice_001.mp4").write_bytes(b"\x00")
            result = benchmark_batch.run_benchmark_batch(in_dir, out_dir)
            json_text = _json.dumps(result)
            csv_text = (out_dir / "benchmark_batch.csv").read_text(encoding="utf-8")
            self.assertNotIn("Patient_Alice_001.mp4", json_text)
            self.assertNotIn("Patient_Alice_001.mp4", csv_text)
            for row in result["per_video"]:
                self.assertNotIn("filename", row)
                self.assertTrue(row["sequence_key"])
        finally:
            shutil.rmtree(in_dir, ignore_errors=True)
            shutil.rmtree(out_dir, ignore_errors=True)

    def test_full_run_with_videos_summarizes(self):
        import shutil
        import tempfile

        bv = _make_bv()
        self._patch_bv(bv)
        in_dir = Path(tempfile.mkdtemp(prefix="bench_in_"))
        out_dir = Path(tempfile.mkdtemp(prefix="bench_out_"))
        try:
            (in_dir / "a.mp4").write_bytes(b"\x00")
            (in_dir / "b.mp4").write_bytes(b"\x00")
            result = benchmark_batch.run_benchmark_batch(in_dir, out_dir)
            self.assertEqual(result["n_videos_requested"], 2)
            self.assertEqual(result["n_videos_requested"], 2)
            self.assertEqual(result["summary"]["REAL_VIDEO_BENCHMARK"], "COMPLETE")
            self.assertEqual(result["summary"]["n_success"], 2)
            self.assertTrue((out_dir / "benchmark_batch.csv").exists())
            self.assertTrue((out_dir / "benchmark_batch.json").exists())
            for row in result["per_video"]:
                self.assertEqual(row["status"], "ok")
                self.assertIn("sequence_key", row)
        finally:
            shutil.rmtree(in_dir, ignore_errors=True)
            shutil.rmtree(out_dir, ignore_errors=True)

    def test_failure_records_sanitized_status(self):
        import shutil
        import tempfile

        self._patch_bv(_make_bv(raises=RuntimeError("boom")))
        tmp = Path(tempfile.mkdtemp(prefix="bench_fail_"))
        try:
            result = benchmark_batch.run_benchmark_batch(None, tmp)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        self.assertEqual(result["summary"]["REAL_VIDEO_BENCHMARK"], "PENDING")


    def test_single_video_produces_compatible_batch(self):
        import json as _json
        import shutil
        import tempfile

        self._patch_bv(_make_bv())
        tmp = Path(tempfile.mkdtemp(prefix="bench_single_"))
        try:
            video = Path(tmp) / "clip.mp4"
            video.write_bytes(b"\x00")
            out = Path(tmp) / "out"
            result = benchmark_batch.run_benchmark_single(video, out, None)
            self.assertEqual(result["summary"]["REAL_VIDEO_BENCHMARK"], "COMPLETE")
            batch = _json.loads((out / "benchmark_batch.json").read_text(encoding="utf-8"))
            self.assertEqual(batch["summary"]["REAL_VIDEO_BENCHMARK"], "COMPLETE")
            self.assertNotIn("clip.mp4", _json.dumps(batch))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

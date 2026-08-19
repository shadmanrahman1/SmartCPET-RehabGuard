"""
Sprint C integration-contract tests (PR #5 final round).

No real network / OpenRouter / camera / KIMORE dataset / model download.
Covers smoke FPS policy, orchestrator correctness, real-vs-synthetic FPS,
release-check contradictions, and report validation.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
EXPERIMENTS = REPO / "experiments" / "biogait"
sys.path.insert(0, str(EXPERIMENTS))
sys.path.insert(0, str(REPO / "biogait"))


class SmokeFpsPolicyTests(unittest.TestCase):
    def test_valid_video_fps_used(self):
        from smoke_runtime import resolve_smoke_fps
        fps, status = resolve_smoke_fps(29.97, True, None)
        self.assertEqual(fps, 29.97)
        self.assertEqual(status, "ok")

    def test_override_when_metadata_invalid(self):
        from smoke_runtime import resolve_smoke_fps
        fps, status = resolve_smoke_fps(0.0, False, 25.0)
        self.assertEqual(fps, 25.0)

    def test_pending_without_metadata_or_override(self):
        from smoke_runtime import resolve_smoke_fps
        fps, status = resolve_smoke_fps(0.0, False, None)
        self.assertIsNone(fps)
        self.assertIn("--fps", status)

    def test_no_silent_30hz_assumption(self):
        from smoke_runtime import resolve_smoke_fps
        fps, status = resolve_smoke_fps(float("nan"), False, None)
        self.assertIsNone(fps)


class RealVideoOrchestratorTests(unittest.TestCase):
    def test_all_planned_script_paths_exist(self):
        from run_real_video_validation import plan_real_video, plan_script_paths_exist
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "clip.mp4"
            video.write_bytes(b"\x00")
            plan = plan_real_video(video, Path(tmp) / "out", fps=30.0)
            missing = plan_script_paths_exist(plan)
            self.assertEqual(missing, [])

    def test_plan_includes_analyze_video_from_biogait_dir(self):
        from run_real_video_validation import plan_real_video
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "clip.mp4"
            video.write_bytes(b"\x00")
            plan = plan_real_video(video, Path(tmp) / "out", fps=None)
            analyze = next(s for s in plan if s["step"] == "offline_analyze")
            self.assertEqual(analyze["script"].name, "analyze_video.py")
            self.assertIn("biogait", str(analyze["script"]))

    def test_plan_aggregate_receives_inputs(self):
        from run_real_video_validation import plan_real_video
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "clip.mp4"
            video.write_bytes(b"\x00")
            out = Path(tmp) / "out"
            plan = plan_real_video(video, out, fps=30.0)
            agg = next(s for s in plan if s["step"] == "aggregate")
            self.assertIn("--inputs", agg["args"])
            self.assertIn("--output-dir", agg["args"])

    def test_failed_step_does_not_yield_complete(self):
        from run_real_video_validation import run_real_video
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "clip.mp4"
            video.write_bytes(b"\x00")
            out = Path(tmp) / "out"
            with mock.patch("subprocess.run", side_effect=RuntimeError("boom")):
                result = run_real_video(video, out, fps=30.0)
            self.assertNotEqual(result["status"], "COMPLETE")
            # No fabricated runtime-complete.
            self.assertNotEqual(result["REAL_VIDEO_RUNTIME"], "COMPLETE")


class RealKimoreOrchestratorTests(unittest.TestCase):
    def test_all_planned_script_paths_exist(self):
        from run_kimore_validation import plan_kimore, plan_script_paths_exist
        with tempfile.TemporaryDirectory() as tmp:
            seq = Path(tmp) / "seq.mat"
            seq.write_bytes(b"\x00")
            plan = plan_kimore(seq, Path(tmp) / "out", fs=30.0)
            self.assertEqual(plan_script_paths_exist(plan), [])

    def test_plan_outputs_normalized_and_evaluation(self):
        from run_kimore_validation import plan_kimore
        with tempfile.TemporaryDirectory() as tmp:
            seq = Path(tmp) / "seq.mat"
            seq.write_bytes(b"\x00")
            out = Path(tmp) / "out"
            plan = plan_kimore(seq, out, fs=30.0)
            steps = {s["step"]: " ".join([str(a) for a in s["args"]]) for s in plan}
            self.assertIn("normalized_sequence.json", steps["parse"])
            self.assertIn("ex5_evaluation.json", steps["evaluate_ex5"])

    def test_plan_fps_uses_sequence_json_not_synthetic(self):
        from run_kimore_validation import plan_kimore
        with tempfile.TemporaryDirectory() as tmp:
            seq = Path(tmp) / "seq.mat"
            seq.write_bytes(b"\x00")
            out = Path(tmp) / "out"
            plan = plan_kimore(seq, out, fs=30.0)
            fps = next(s for s in plan if s["step"] == "fps_sensitivity")
            joined = " ".join(str(a) for a in fps["args"])
            self.assertIn("--sequence-json", joined)
            self.assertNotIn("--synthetic", joined)

    def test_failed_parse_never_complete(self):
        from run_kimore_validation import run_kimore
        with tempfile.TemporaryDirectory() as tmp:
            seq = Path(tmp) / "seq.mat"
            seq.write_bytes(b"\x00")
            out = Path(tmp) / "out"
            with mock.patch("subprocess.run", side_effect=RuntimeError("boom")):
                result = run_kimore(seq, out, fs=30.0)
            self.assertEqual(result["REAL_KIMORE_VALIDATION"], "FAILED")


class RealVsSyntheticFpsTests(unittest.TestCase):
    def _seq_json(self, fs, origin):
        sys.path.insert(0, str(EXPERIMENTS))
        from kimore_adapter import synthetic_ex5_sequence
        seq = synthetic_ex5_sequence(120, 30.0, seed=0)
        seq["sampling_rate_hz"] = fs
        seq["data_origin"] = origin
        return seq

    def test_real_30hz_drives_real_fps(self):
        from fps_sensitivity import main as fps_main
        seq = self._seq_json(30.0, "REAL_KIMORE_NATIVE_SKELETON")
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "seq.json"
            out = Path(tmp) / "fps.json"
            src.write_text(json.dumps(seq), encoding="utf-8")
            fps_main(["--sequence-json", str(src), "--output", str(out)])
            result = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(result["data_origin"], "REAL_KIMORE_NATIVE_SKELETON")
            self.assertNotEqual(result.get("status"), "PENDING_VALID_30HZ_ANCHOR")

    def test_non_30hz_source_skips_anchor(self):
        from fps_sensitivity import main as fps_main
        seq = self._seq_json(25.0, "REAL_KIMORE_NATIVE_SKELETON")
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "seq.json"
            out = Path(tmp) / "fps.json"
            src.write_text(json.dumps(seq), encoding="utf-8")
            fps_main(["--sequence-json", str(src), "--output", str(out)])
            result = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "PENDING_VALID_30HZ_ANCHOR")


class ReleaseCheckContractTests(unittest.TestCase):
    def _write_status(self, tmp, statuses):
        path = Path(tmp) / "status.json"
        path.write_text(json.dumps({"statuses": statuses}, allow_nan=False), encoding="utf-8")
        return path

    def common(self):
        return {
            "unit_tests": "COMPLETE", "ci": "COMPLETE",
            "fps_sensitivity_synthetic": "COMPLETE",
            "missingness_sensitivity_synthetic": "COMPLETE",
            "landmark_robustness_synthetic": "COMPLETE",
            "real_video_smoke": "PENDING", "runtime_benchmark_real_video": "PENDING",
            "kimore_adapter_real_data": "PENDING",
        }

    def test_nested_pending_dict_not_complete(self):
        from release_check import _status_complete
        self.assertFalse(_status_complete({"PENDING": True}))
        self.assertTrue(_status_complete({"sprint_c": {"a": "COMPLETE"}}))
        self.assertFalse(_status_complete({"PENDING": {"x": "PENDING"}}))

    def test_empirical_primary_requires_real_success(self):
        from release_check import check
        statuses = self.common()
        statuses.update({"real_video_smoke": "PENDING", "runtime_benchmark_real_video": "COMPLETE",
                         "kimore_adapter_real_data": "PENDING"})
        with tempfile.TemporaryDirectory() as tmp:
            result = check(self._write_status(tmp, statuses))
            # primary can never claim empirical unless empirical_ready.
            self.assertNotEqual(result["primary"], "READY_FOR_EMPIRICAL_RESULTS")
            self.assertEqual(result["empirical_results"], "NOT_READY_FOR_EMPIRICAL_RESULTS")

    def test_real_success_enables_empirical(self):
        from release_check import check
        statuses = self.common()
        statuses.update({"real_video_smoke": "COMPLETE", "runtime_benchmark_real_video": "COMPLETE",
                         "kimore_adapter_real_data": "COMPLETE",
                         "kimore_ex5_evaluation_real": "COMPLETE"})
        with tempfile.TemporaryDirectory() as tmp:
            result = check(self._write_status(tmp, statuses))
            self.assertEqual(result["primary"], "READY_FOR_EMPIRICAL_RESULTS")
            self.assertEqual(result["empirical_results"], "READY_FOR_EMPIRICAL_RESULTS")


class ReportValidationTests(unittest.TestCase):
    def test_malformed_session_rejected(self):
        from generate_research_report import build_report
        with self.assertRaises(ValueError):
            build_report(["not", "a", "dict"])
        with self.assertRaises(ValueError):
            build_report({"left_knee": float("nan")})

    def test_identity_key_rejected(self):
        from generate_research_report import build_report
        with self.assertRaises(ValueError):
            build_report({"data_origin": "REAL_VIDEO_MEDIAPIPE", "patient_name": "x"})


if __name__ == "__main__":
    unittest.main()

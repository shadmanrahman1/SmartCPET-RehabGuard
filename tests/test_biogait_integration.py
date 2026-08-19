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


class EndToEndContractTests(unittest.TestCase):
    """Expose the previously-missed execution bugs (item 15 A-J)."""

    def test_run_explanation_nested_sensitive_no_network(self):
        from explanation_ui import run_explanation
        from openrouter_explainer import OpenRouterExplainer

        explainer = OpenRouterExplainer(mode="openrouter", api_key="sk-test-abcdef123", model="m1",
                                        base_url="https://openrouter.ai/api/v1")
        evidence = {"quality": {"available": True, "api_key": "sk-secret",
                                "camera_url": "http://cam", "participant_id": "7"}}
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("no network")):
            audit = run_explanation(evidence, explainer=explainer)
        self.assertEqual(audit["status"], "INPUT_CONTAINS_SENSITIVE_NO_REMOTE")
        self.assertIsNone(audit["provider"])

    def test_run_explanation_empty_payload_no_remote(self):
        from explanation_ui import run_explanation
        from openrouter_explainer import OpenRouterExplainer

        # Unconfigured openrouter -> NO remote, template fallback.
        explainer = OpenRouterExplainer(mode="openrouter", api_key="", model="",
                                        base_url="https://openrouter.ai/api/v1")
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("no network")):
            audit = run_explanation({}, explainer=explainer)
        self.assertEqual(audit["status"], "OPENROUTER_NOT_CONFIGURED")
        # Deterministic template fallback is always a clinical-free note.
        self.assertIn("not a clinical assessment", audit["output"]["safety_note"])

    def test_real_video_aggregate_inputs_not_empty_before_files(self):
        from run_real_video_validation import plan_real_video
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "clip.mp4"
            video.write_bytes(b"\x00")
            out = Path(tmp) / "out"  # result files do NOT exist yet
            plan = plan_real_video(video, out, fps=30.0)
            agg = next(s for s in plan if s["step"] == "aggregate")
            idx = agg["args"].index("--inputs")
            parsed = json.loads(agg["args"][idx + 1])
            self.assertIn("session", parsed)
            self.assertIn("smoke", parsed)
            self.assertIn("benchmark", parsed)
            self.assertNotEqual(parsed, {})

    def test_release_step_is_after_status_creation(self):
        from run_real_video_validation import plan_real_video
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "clip.mp4"
            video.write_bytes(b"\x00")
            out = Path(tmp) / "out"
            plan = plan_real_video(video, out, fps=30.0)
            release = next(s for s in plan if s["step"] == "release_check")
            self.assertEqual(release["phase"], 3)
            self.assertIn("--evaluation-status", release["args"])

    def test_kimore_adapter_load_fs_and_origin(self):
        import kimore_adapter
        from kimore_adapter import main as kimore_main

        fake_joints = {"left_knee": {"x": [1.0, 2.0], "y": [1.0, 2.0], "z": [0.0, 0.0]},
                       "right_knee": {"x": [2.0, 3.0], "y": [1.0, 2.0], "z": [0.0, 0.0]}}
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "seq.mat"
            src.write_bytes(b"\x00")
            out = Path(tmp) / "norm.json"
            with mock.patch.object(kimore_adapter, "parse_joint_table", return_value=fake_joints):
                kimore_main(["--load", str(src), "--fs", "30", "--output", str(out)])
            seq = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(seq["sampling_rate_hz"], 30.0)
            self.assertEqual(seq["data_origin"], "REAL_KIMORE_NATIVE_SKELETON")
            self.assertEqual(seq["validation_status"], "PARSED_SEQUENCE_VALIDATED")

    def test_kimore_plan_fps_consumes_normalized_and_aggregate_inputs_nonempty(self):
        from run_kimore_validation import plan_kimore
        with tempfile.TemporaryDirectory() as tmp:
            seq = Path(tmp) / "seq.mat"
            seq.write_bytes(b"\x00")
            out = Path(tmp) / "out"
            plan = plan_kimore(seq, out, fs=30.0)
            fps = next(s for s in plan if s["step"] == "fps_sensitivity")
            agg = next(s for s in plan if s["step"] == "aggregate")
            self.assertIn(str(out / "normalized_sequence.json"), [str(a) for a in fps["args"]])
            idx = agg["args"].index("--inputs")
            parsed = json.loads(agg["args"][idx + 1])
            self.assertIn("evaluation", parsed)
            self.assertIn("fps_sensitivity", parsed)
            self.assertNotEqual(parsed, {})

    def test_kimore_conference_after_status_file(self):
        from run_kimore_validation import plan_kimore
        with tempfile.TemporaryDirectory() as tmp:
            seq = Path(tmp) / "seq.mat"
            seq.write_bytes(b"\x00")
            out = Path(tmp) / "out"
            plan = plan_kimore(seq, out, fs=30.0)
            conference = next(s for s in plan if s["step"] == "conference")
            self.assertEqual(conference["phase"], 3)
            self.assertIn(str(out / "evaluation_status.json"), [str(a) for a in conference["args"]])

    def test_release_requires_kimore_ex5_evaluation(self):
        from release_check import check
        statuses = self._common_status()
        statuses.update({"real_video_smoke": "COMPLETE", "runtime_benchmark_real_video": "COMPLETE",
                         "kimore_adapter_real_data": "COMPLETE",
                         "kimore_ex5_evaluation_real": "PENDING"})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "status.json"
            path.write_text(json.dumps({"statuses": statuses}, allow_nan=False), encoding="utf-8")
            result = check(path)
            self.assertEqual(result["empirical_results"], "NOT_READY_FOR_EMPIRICAL_RESULTS")
            self.assertNotEqual(result["primary"], "READY_FOR_EMPIRICAL_RESULTS")

    def _common_status(self):
        return {
            "unit_tests": "COMPLETE", "ci": "COMPLETE",
            "fps_sensitivity_synthetic": "COMPLETE",
            "missingness_sensitivity_synthetic": "COMPLETE",
            "landmark_robustness_synthetic": "COMPLETE",
        }

    def test_release_dict_status_compound_not_one_leaf(self):
        from release_check import _status_complete
        self.assertFalse(_status_complete({"parse": "COMPLETE", "evaluation": "PENDING"}))
        self.assertTrue(_status_complete({"parse": "COMPLETE", "evaluation": "COMPLETE"}))
        self.assertFalse(_status_complete({"status": "PENDING"}))
        self.assertTrue(_status_complete({"status": "COMPLETE"}))


if __name__ == "__main__":
    unittest.main()

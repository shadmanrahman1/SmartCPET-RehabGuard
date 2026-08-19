"""
Tests for Sprint C productization tools (C12/C13/C16/C17/C18).

No real LLM, no network, no camera, no KIMORE dataset.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "experiments" / "biogait"))
sys.path.insert(0, str(REPO / "biogait"))

from common import atomic_json_write  # noqa: E402


def _session():
    return {
        "schema_version": "1.0",
        "module": "biogait",
        "exercise": "kimore_ex5_squat",
        "data_origin": "REAL_VIDEO_MEDIAPIPE",
        "processing_mode": "offline_mediapipe_video",
        "po_coverage": {"left": 0.9, "right": 0.9},
        "control_factor_coverage": {"torso_area_m2": 1.0},
        "descriptive": {"left_knee_rom_deg": 40.0},
        "temporal_analysis": {"reference": {"classification": "REFERENCE_DERIVED", "left": {}, "right": {}}},
        "quality_summary": {"frames_added": 100, "available_frames": 84},
        "limitations": ["Not a clinical score."],
    }


class ReportTests(unittest.TestCase):
    def test_report_generation(self):
        from generate_research_report import build_report, json_summary

        text = build_report(_session())
        self.assertIn("BioGait Research Evidence Report", text)
        self.assertIn("REAL_VIDEO_MEDIAPIPE", text)
        self.assertIn("not a clinical", text.lower())
        summary = json_summary(_session())
        self.assertEqual(summary["data_origin"], "REAL_VIDEO_MEDIAPIPE")

    def test_report_not_called_clinical(self):
        from generate_research_report import build_report

        text = build_report(_session())
        self.assertNotIn("Clinical Report", text)
        self.assertNotIn("Diagnostic Report", text)


class ConferenceArtifactsTests(unittest.TestCase):
    def test_generate_artifacts(self):
        from conference_artifacts import generate

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "artifacts"
            status = Path(tmp) / "eval_status.json"
            atomic_json_write(status, {"statuses": {"kimore_adapter_real_data": "PENDING",
                                                     "runtime_benchmark_real_video": "PENDING"}})
            result = generate(out, status)
            self.assertTrue((out / "architecture_summary.md").exists())
            self.assertTrue((out / "method_summary.md").exists())
            self.assertTrue((out / "claim_status.md").exists())
            results_md = (out / "results_status.md").read_text(encoding="utf-8")
            self.assertIn("REAL_KIMORE_DATA", results_md)
            self.assertIn("MEDIAPIPE_VS_KINECT: DEFERRED", results_md)
            self.assertIn("results_status.md", result["written"])


class ReleaseCheckTests(unittest.TestCase):
    def _status(self, overrides):
        base = {
            "unit_tests": "COMPLETE", "ci": "COMPLETE",
            "kimore_adapter_real_data": "PENDING",
            "real_video_smoke": "PENDING", "runtime_benchmark_real_video": "PENDING",
            "kimore_ex5_evaluation_real": "PENDING",
            "fps_sensitivity_synthetic": "COMPLETE",
            "missingness_sensitivity_synthetic": "COMPLETE",
            "landmark_robustness_synthetic": "COMPLETE",
        }
        base.update(overrides)
        return base

    def test_code_demo_ready_with_synthetic(self):
        from release_check import check

        st = {"unit_tests": "COMPLETE", "ci": "COMPLETE",
              "fps_sensitivity_synthetic": "COMPLETE",
              "missingness_sensitivity_synthetic": "COMPLETE",
              "landmark_robustness_synthetic": "COMPLETE"}
        checks = check.__globals__  # noqa
        # Provide a status path with the fields.
        status = {"statuses": st}
        from evidence_schema import validate_evidence_record as _v
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.json"
            atomic_json_write(path, status)
            result = check(path)
            self.assertEqual(result["empirical_results"], "NOT_READY_FOR_EMPIRICAL_RESULTS")
            self.assertIn("READY_FOR_CODE_DEMO", result["release_check"])
            self.assertNotIn("clinically", result["note"].lower())

    def test_note_is_not_clinical(self):
        import json
        from release_check import check

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.json"
            atomic_json_write(path, {"statuses": self._status({})})
            out = json.dumps(check(path)).lower()
            for banned in ("clinically ready", "medical ready", "deployment ready"):
                self.assertNotIn(banned, out)


class OrchestratorTests(unittest.TestCase):
    def test_real_video_dry_run(self):
        from run_real_video_validation import plan_real_video

        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "clip.mp4"
            video.write_bytes(b"\x00")
            steps = plan_real_video(video, Path(tmp) / "out", fps=30.0)
            names = [s["step"] for s in steps]
            self.assertIn("smoke", names)
            self.assertIn("offline_analyze", names)
            self.assertIn("benchmark", names)
            self.assertIn("release_check", names)

    def test_kimore_dry_run_requires_fs_note(self):
        from run_kimore_validation import run_kimore

        with tempfile.TemporaryDirectory() as tmp:
            seq = Path(tmp) / "seq.mat"
            seq.write_bytes(b"\x00")
            out = Path(tmp) / "out"
            result = run_kimore(seq, out, fs=None, dry_run=True)
            self.assertTrue(result["sampling_rate_required"])
            self.assertEqual(result["REAL_KIMORE_VALIDATION"], "DRY_RUN")

    def test_orchestrator_missing_file_raises(self):
        from run_real_video_validation import run_real_video

        with self.assertRaises(FileNotFoundError):
            run_real_video(Path("definitely_missing.mp4"), Path("x"), None, dry_run=True)


if __name__ == "__main__":
    unittest.main()

"""Conference artifact exporter (Sprint C, C13).

From valid result/evaluation files, generate neutral data files for paper
writing: architecture_summary.md, method_summary.md, claim_status.md,
results_status.md, table_manifest.json, figure_manifest.json.

Nothing is fabricated: unavailable results are marked
REAL_KIMORE_DATA=PENDING / REAL_VIDEO_RUNTIME=PENDING /
MEDIAPIPE_VS_KINECT=DEFERRED where still true.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

from common import atomic_json_write, load_json

ARCHITECTURE_MD = """# BioGait Architecture Summary (Sprint C)

- RGB source (live camera or offline local video) -> MediaPipe PoseLandmarker
  Lite (`pose_landmarker_lite.task`).
- World-landmark evidence (`evidence_features.py`) -> Session accumulator
  (`session_analysis.py`) -> live research panel / session export.
- Source-aligned KIMORE reference analysis + ACTUAL-fps adapted analysis
  (`reference_temporal.py`).
- Bounded explanation layer: deterministic template (default) and optional
  OpenRouter remote explainer (`template` / `openrouter` modes).
- Offline research report (`generate_research_report.py`).
- No CPET node; CPET is outside the active Sprint-C architecture scope.
"""

METHOD_MD = """# BioGait Method Summary (Sprint C)

- Input: MediaPipe world landmarks (3D meters, hip-midpoint origin).
- Pose model: PoseLandmarker Lite with engineering confidence settings.
- Feature geometry: source-aligned sagittal knee angle (reviewed atan2
  equation) + feature-specific quality gating.
- Reference filter: FIXED order-3 / 1 Hz / 30 Hz ba-form butter + filtfilt.
- Adapted filter: order-3 / 1 Hz at the actual frame rate.
- Temporal candidates at max/sqrt(2); min peak distance floor(n/10).
- KIMORE source alignment: MATLAB 10:end -> discard first 9 zero-based samples.
- Explanation layer: bounded, structured-evidence-only; no clinical score.
"""

CLAIM_STATUS = """# BioGait Claim Status (Sprint C)

| Claim | Status |
|-------|--------|
| Source-aligned KIMORE-informed feature extraction | Tooling complete; real-data validation PENDING |
| MediaPipe world-landmark representation | ENGINEERING_ADAPTED (not equivalent to Kinect) |
| Candidate temporal events | Candidates, not clinically validated repetitions |
| Clinical score / diagnosis / treatment | NOT produced anywhere |
| MediaPipe-vs-Kinect numerical validation | DEFERRED |
"""


def results_status_md(evaluation_status: dict) -> str:
    statuses = evaluation_status.get("statuses", {}) if isinstance(evaluation_status, dict) else {}
    lines = ["# BioGait Results Status (Sprint C)", ""]
    for key in ("unit_tests", "ci", "kimore_adapter_real_data",
                "kimore_ex5_evaluation_real", "fps_sensitivity_synthetic",
                "missingness_sensitivity_synthetic", "landmark_robustness_synthetic",
                "runtime_benchmark_real_video", "real_video_smoke",
                "mediapipe_vs_kinect_validation"):
        if key in statuses:
            lines.append(f"- {key}: {statuses[key]}")
    lines.append("- REAL_KIMORE_DATA: " + (
        "pending/not-validated"
        if statuses.get("kimore_adapter_real_data", "PENDING") != "COMPLETE"
        else "validated"))
    lines.append("- REAL_VIDEO_RUNTIME: " + (
        "pending"
        if statuses.get("runtime_benchmark_real_video", "PENDING") != "COMPLETE"
        else "available"))
    lines.append("- MEDIAPIPE_VS_KINECT: DEFERRED")
    return "\n".join(lines)


def _status_cell(evaluation_status: dict, key: str, default: str) -> str:
    statuses = evaluation_status.get("statuses", {}) if isinstance(evaluation_status, dict) else {}
    return statuses.get(key, default)


def _derive_table5(evaluation_status: Optional[dict]) -> str:
    if evaluation_status is None:
        return "PENDING_DATA"
    if _status_cell(evaluation_status, "runtime_benchmark_real_video", "PENDING") == "COMPLETE":
        return "EMPIRICAL_COMPLETE"
    return "PENDING_DATA"


def _derive_table6(evaluation_status: Optional[dict]) -> str:
    if evaluation_status is None:
        return "PENDING_DATA"
    if _status_cell(evaluation_status, "kimore_fps_sensitivity_real", "PENDING") == "COMPLETE":
        return "EMPIRICAL_COMPLETE"
    if _status_cell(evaluation_status, "fps_sensitivity_synthetic", "COMPLETE") == "COMPLETE":
        return "SYNTHETIC_ONLY"
    return "PENDING_DATA"


def generate(output_dir: Path, evaluation_status_path: Optional[Path]) -> dict:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    evaluation_status = load_json(evaluation_status_path) if evaluation_status_path else None

    (output_dir / "architecture_summary.md").write_text(ARCHITECTURE_MD, encoding="utf-8")
    (output_dir / "method_summary.md").write_text(METHOD_MD, encoding="utf-8")
    (output_dir / "claim_status.md").write_text(CLAIM_STATUS, encoding="utf-8")
    (output_dir / "results_status.md").write_text(
        results_status_md(evaluation_status or {}), encoding="utf-8"
    )

    table4 = "SYNTHETIC_ONLY"  # landmark robustness is synthetic-only today
    table5 = _derive_table5(evaluation_status)
    table6 = _derive_table6(evaluation_status)
    table_manifest = {
        "schema_version": "1.0",
        "tables": {
            "table1_components": {"status": "COMPLETE"},
            "table2_kimore_mapping": {"status": "COMPLETE"},
            "table3_protocol": {"status": "COMPLETE"},
            "table4_robustness": {"status": table4},
            "table5_runtime_benchmark": {"status": table5},
            "table6_fps_sensitivity": {"status": table6},
        },
        "note": "Numeric table statuses are data-driven; SYNTHETIC_ONLY/PENDING_DATA are not empirical results.",
    }
    figure_d = "EMPIRICAL_COMPLETE" if table5 == "EMPIRICAL_COMPLETE" else "PENDING_DATA"
    figure_manifest = {
        "schema_version": "1.0",
        "figures": {
            "A": "PENDING_DATA",
            "B": table6,
            "C": "SYNTHETIC_ONLY" if _status_cell(evaluation_status or {}, "missingness_sensitivity_synthetic", "COMPLETE") == "COMPLETE" else "PENDING_DATA",
            "D": figure_d,
            "E": "SYNTHETIC_ONLY",
        },
        "note": "Figures are data-gated; synthetic-only figures are software validation, not empirical.",
    }
    atomic_json_write(output_dir / "table_manifest.json", table_manifest)
    atomic_json_write(output_dir / "figure_manifest.json", figure_manifest)
    return {
        "output_dir": str(output_dir),
        "written": [
            "architecture_summary.md", "method_summary.md", "claim_status.md",
            "results_status.md", "table_manifest.json", "figure_manifest.json",
        ],
        "table_statuses": {"table4": table4, "table5": table5, "table6": table6},
    }


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="conference_artifacts", description="Emit neutral conference artifacts.")
    p.add_argument("--output-dir", required=True)
    p.add_argument("--evaluation-status", default=None)
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    result = generate(Path(args.output_dir), Path(args.evaluation_status) if args.evaluation_status else None)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

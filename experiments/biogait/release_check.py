"""BioGait release readiness checker (Sprint C, C16).

Inspects engineering/research status and outputs one of:
    READY_FOR_CODE_DEMO
    READY_FOR_SYNTHETIC_METHODS_REPORT
    NOT_READY_FOR_EMPIRICAL_RESULTS

These are engineering/research statuses. It never says "clinically ready",
"deployment ready", or "medical ready".
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Optional

from common import BIOGAIT_DIR, load_json

_DEFAULT_STATUS = Path(__file__).resolve().parent / "results" / "evaluation_status.json"


def check(status_path: Optional[Path] = None) -> dict[str, Any]:
    status = load_json(status_path) if status_path else load_json(_DEFAULT_STATUS)
    statuses = status.get("statuses", {}) if isinstance(status, dict) else {}

    unit_tests = statuses.get("unit_tests", "PENDING")
    ci = statuses.get("ci", "PENDING")
    model_present = (BIOGAIT_DIR / "pose_landmarker_lite.task").exists()
    real_video_smoke = statuses.get("real_video_smoke", "PENDING")
    real_benchmark = statuses.get("runtime_benchmark_real_video", "PENDING")
    real_kimore = statuses.get("kimore_adapter_real_data", "PENDING")
    synthetic_ok = all(
        statuses.get(k, "PENDING") in ("COMPLETE", "IMPLEMENTED_REAL_DATA_PENDING")
        or isinstance(statuses.get(k), (dict,))
        for k in ("fps_sensitivity_synthetic", "missingness_sensitivity_synthetic",
                  "landmark_robustness_synthetic")
    )
    claim_matrix_present = (Path(__file__).resolve().parents[2] / "docs" / "biogait-claim-matrix.md").exists()
    methods_snapshot_present = (Path(__file__).resolve().parents[2] / "docs" / "biogait-methods-snapshot.md").exists()

    checks = {
        "unit_tests": unit_tests,
        "ci": ci,
        "model_file_present": model_present,
        "real_video_smoke": real_video_smoke,
        "runtime_benchmark_real_video": real_benchmark,
        "real_kimore_validation": real_kimore,
        "synthetic_experiments_ok": synthetic_ok,
        "claim_matrix_present": claim_matrix_present,
        "methods_snapshot_present": methods_snapshot_present,
    }

    code_demo_ready = (
        unit_tests == "COMPLETE" and model_present and claim_matrix_present
        and methods_snapshot_present
    )
    empirical_ready = (
        code_demo_ready
        and real_video_smoke == "COMPLETE"
        and real_benchmark == "COMPLETE"
        and real_kimore == "COMPLETE"
    )

    if empirical_ready:
        release_state = "READY_FOR_EMPIRICAL_RESULTS"
    elif code_demo_ready:
        release_state = "READY_FOR_CODE_DEMO_AND_SYNTHETIC_METHODS_REPORT"
    else:
        release_state = "NOT_READY"

    # Normalized primary output per spec.
    if real_kimore == "COMPLETE" and real_video_smoke == "COMPLETE":
        primary = "READY_FOR_EMPIRICAL_RESULTS"
    elif code_demo_ready or synthetic_ok:
        primary = "READY_FOR_CODE_DEMO / READY_FOR_SYNTHETIC_METHODS_REPORT"
    else:
        primary = "NOT_READY_FOR_EMPIRICAL_RESULTS"

    return {
        "release_check": "READY_FOR_CODE_DEMO" if code_demo_ready else (
            "READY_FOR_SYNTHETIC_METHODS_REPORT" if synthetic_ok else "NOT_READY"
        ),
        "empirical_results": "READY_FOR_EMPIRICAL_RESULTS" if empirical_ready else "NOT_READY_FOR_EMPIRICAL_RESULTS",
        "checks": checks,
        "primary": primary,
        "note": (
            "Engineering/research statuses only. This is not a clinical, "
            "deployment, or medical-readiness statement."
        ),
    }


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="release_check", description="BioGait release readiness checker.")
    p.add_argument("--evaluation-status", default=None)
    p.add_argument("--print", action="store_true", default=True, help=argparse.SUPPRESS)
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    import json
    result = check(Path(args.evaluation_status) if args.evaluation_status else None)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

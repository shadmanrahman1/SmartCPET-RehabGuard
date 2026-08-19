"""Real KIMORE validation orchestrator (Sprint C, C18; integration-fixed).

Requires an explicit local skeletal file via ``--load PATH`` and ``--fs`` when
the sampling rate cannot be derived. It never downloads KIMORE and never
silently assumes a sampling rate. FPS sensitivity for a real KIMORE run uses the
REAL normalized sequence (never the synthetic fixture) and is skipped unless a
valid 30 Hz anchor exists.

Pipeline:
    parse -> normalized_sequence.json
    evaluate Ex5 -> ex5_evaluation.json   (data_origin set on successful parse)
    FPS sensitivity -> fps_sensitivity.json (real 30-Hz source only)
    aggregate / paper / conference / status

Status (honest): COMPLETE / PARTIAL_GEOMETRY_ONLY / FAILED / DRY_RUN / PENDING.
COMPLETE requires successful parse + structural validation + Ex5 evaluation and
reports temporal/FPS sub-status separately.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS_DIR = Path(__file__).resolve().parent
RESULTS_DIR = EXPERIMENTS_DIR / "results"

_PY = sys.executable


def plan_kimore(load_path: Path, output_dir: Path, fs: Optional[float]) -> list[dict]:
    out = Path(output_dir)
    parse_cmd = ["parse", EXPERIMENTS_DIR / "kimore_adapter.py",
                 "--load", str(load_path), "--output", str(out / "normalized_sequence.json")]
    evaluate_cmd = ["evaluate_ex5", EXPERIMENTS_DIR / "evaluate_kimore_ex5.py",
                    "--sequence-json", str(out / "normalized_sequence.json"),
                    "--output", str(out / "ex5_evaluation.json")]
    if fs is not None:
        evaluate_cmd += ["--fs", str(fs)]
    # FPS sensitivity uses the REAL normalized sequence ONLY (never --synthetic).
    fps_cmd = ["fps_sensitivity", EXPERIMENTS_DIR / "fps_sensitivity.py",
               "--sequence-json", str(out / "normalized_sequence.json"),
               "--output", str(out / "fps_sensitivity.json")]
    aggregate_cmd = ["aggregate", EXPERIMENTS_DIR / "aggregate_results.py",
                     "--inputs", "{}", "--output-dir", str(out / "aggregate")]
    paper_cmd = ["paper_tables", EXPERIMENTS_DIR / "make_paper_tables.py",
                 "--input-dir", str(out), "--output-dir", str(out / "paper")]
    conference_cmd = ["conference", EXPERIMENTS_DIR / "conference_artifacts.py",
                      "--output-dir", str(out / "conference"),
                      "--evaluation-status", str(out / "evaluation_status.json")]
    mapping_cmd = ["mapping_report", EXPERIMENTS_DIR / "kimore_mapping_report.py",
                   "--output-dir", str(out / "mapping")]
    return [
        {"step": c[0], "script": Path(c[1]), "args": c[2:]} for c in
        (parse_cmd, evaluate_cmd, fps_cmd, aggregate_cmd, paper_cmd, conference_cmd, mapping_cmd)
    ]


def plan_script_paths_exist(plan: list[dict]) -> list[str]:
    return [str(s["script"]) for s in plan if not Path(s["script"]).exists()]


def _read_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def atomic_json_write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def run_kimore(load_path: Path, output_dir: Path, fs: Optional[float], dry_run: bool = False) -> dict:
    if not load_path.exists():
        raise FileNotFoundError(f"KIMORE file does not exist: {load_path}")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    plan = plan_kimore(load_path, output_dir, fs)
    results: list[dict] = []
    for step in plan:
        if dry_run:
            results.append({"step": step["step"], "status": "DRY_RUN"})
            continue
        cmd = [_PY, str(step["script"])] + [str(a) for a in step["args"]]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            results.append({"step": step["step"], "status": "ok"})
        except Exception:  # noqa: BLE001 - record sanitized failure
            results.append({"step": step["step"], "status": "failed", "error_type": "subprocess"})

    ok_steps = [r for r in results if r["status"] == "ok"]
    failed_steps = [r for r in results if r["status"] == "failed"]
    if dry_run:
        overall = "DRY_RUN"
    elif failed_steps and not ok_steps:
        overall = "FAILED"
    else:
        overall = "PARTIAL_GEOMETRY_ONLY"

    # Determine temporal/FPS sub-status from the produced artifacts.
    eval_result = _read_json(output_dir / "ex5_evaluation.json")
    fps_result = _read_json(output_dir / "fps_sensitivity.json")
    parse_succeeded = bool(
        not dry_run
        and any(r["step"] == "parse" and r["status"] == "ok" for r in results)
        and (output_dir / "normalized_sequence.json").exists()
    )
    eval_complete = bool(
        not dry_run and isinstance(eval_result, dict)
        and eval_result.get("execution_status") == "COMPLETE"
        and eval_result.get("data_origin") == "REAL_KIMORE_NATIVE_SKELETON"
    )
    temporal_ok = bool(
        eval_complete and isinstance(eval_result, dict)
        and eval_result.get("sampling_rate_status") == "ok"
    )
    fps_ran_real = bool(
        not dry_run and isinstance(fps_result, dict)
        and fps_result.get("data_origin") == "REAL_KIMORE_NATIVE_SKELETON"
        and fps_result.get("status") != "PENDING_VALID_30HZ_ANCHOR"
    )

    if parse_succeeded and eval_complete and temporal_ok:
        overall = "COMPLETE"
    elif (parse_succeeded and eval_complete and not temporal_ok) or overall == "PARTIAL_GEOMETRY_ONLY":
        overall = "PARTIAL_GEOMETRY_ONLY"

    real_kimore = (
        "COMPLETE" if (parse_succeeded and eval_complete and temporal_ok)
        else ("DRY_RUN" if dry_run else (
            "PARTIAL_GEOMETRY_ONLY" if (parse_succeeded and eval_complete) else (
                "FAILED" if failed_steps else "PENDING"))
        )
    )

    local_status = {
        "statuses": {
            "kimore_adapter_real_data": "COMPLETE" if parse_succeeded and eval_complete else "PENDING",
            "kimore_ex5_evaluation_real": (
                "COMPLETE" if eval_complete else ("PENDING" if not dry_run else "DRY_RUN")
            ),
            "kimore_temporal_analysis": "COMPLETE" if temporal_ok else ("GEOMETRY_ONLY_TEMPORAL_PENDING" if eval_complete else "PENDING"),
            "kimore_fps_sensitivity_real": "COMPLETE" if fps_ran_real else "PENDING",
        },
        "note": "Real-data statuses reflect actual execution; inferred from parsed artifacts, never fabricated.",
    }
    atomic_json_write(output_dir / "evaluation_status.json", local_status)

    summary = {
        "orchestrator": "run_kimore_validation",
        "real_kimore_sequence": True,
        "sampling_rate_required": fs is None,
        "dry_run": dry_run,
        "REAL_KIMORE_VALIDATION": real_kimore,
        "temporal_status": "COMPLETE" if temporal_ok else ("GEOMETRY_ONLY_TEMPORAL_PENDING" if eval_complete else "PENDING"),
        "fps_sensitivity_status": "COMPLETE" if fps_ran_real else ("PENDING_VALID_30HZ_ANCHOR" if isinstance(fps_result, dict) and fps_result.get("status") == "PENDING_VALID_30HZ_ANCHOR" else "PENDING"),
        "steps": results,
        "evaluation_status_file": "evaluation_status.json",
    }
    atomic_json_write(output_dir / "kimore_validation.json", summary)
    return summary


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="run_kimore_validation", description="Orchestrate real KIMORE validation.")
    p.add_argument("--load", required=True, help="explicit local KIMORE skeletal file")
    p.add_argument("--fs", type=float, default=None, help="sampling rate (required if not derivable)")
    p.add_argument("--output-dir", default=str(RESULTS_DIR / "kimore_ex5"))
    p.add_argument("--dry-run", action="store_true")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    result = run_kimore(Path(args.load), Path(args.output_dir), args.fs, args.dry_run)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

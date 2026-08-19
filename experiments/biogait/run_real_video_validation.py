"""Real-video validation orchestrator (Sprint C, C17; integration-fixed).

Convenient explicit command path for when a real, non-sensitive test video is
available. Requires explicit ``--video PATH``. It never searches the computer
for videos, never uploads, and never commits the video. Scripts are resolved by
their real locations (analyze_video.py lives under biogait/, the rest under
experiments/biogait/).

Pipeline (steps recorded with honest per-step status):
    smoke -> offline_analyze -> benchmark -> aggregate -> paper-table refresh
    -> figure refresh (if matplotlib) -> release-check refresh

Status semantics: COMPLETE only when every required step actually succeeds;
PARTIAL when at least one succeeds; FAILED when none do; DRY_RUN for dry runs.
REAL_VIDEO_RUNTIME is COMPLETE only when the real smoke+runtime-benchmark
requirements succeed. A local ``<output_dir>/evaluation_status.json`` is written
from actual execution (never fabricated) and passed to release_check.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
BIOGAIT_DIR = REPO_ROOT / "biogait"
EXPERIMENTS_DIR = Path(__file__).resolve().parent
RESULTS_DIR = EXPERIMENTS_DIR / "results"

_PY = sys.executable


def _inputs_map(output_dir: Path) -> str:
    files = {}
    for label, name in (("session", "session.json"), ("smoke", "smoke.json"),
                        ("benchmark", "benchmark_batch.json")):
        if (output_dir / name).exists():
            files[label] = str(output_dir / name)
    return json.dumps(files)


def plan_real_video(video: Path, output_dir: Path, fps: Optional[float]) -> list[dict]:
    out = Path(output_dir)
    build_cmd = ["offline_analyze", BIOGAIT_DIR / "analyze_video.py",
                 "--input", str(video), "--output", str(out / "session.json")]
    if fps is not None:
        build_cmd += ["--fps", str(fps)]
    smoke_cmd = ["smoke", EXPERIMENTS_DIR / "smoke_runtime.py",
                 "--video", str(video), "--output", str(out / "smoke.json")]
    if fps is not None:
        smoke_cmd += ["--fps", str(fps)]
    bench_cmd = ["benchmark",
                 EXPERIMENTS_DIR / "benchmark_batch.py",
                 "--video", str(video), "--output-dir", str(out)]
    if fps is not None:
        bench_cmd += ["--fps", str(fps)]
    aggregate_cmd = ["aggregate",
                     EXPERIMENTS_DIR / "aggregate_results.py",
                     "--inputs", _inputs_map(out),
                     "--output-dir", str(out / "aggregate")]
    paper_cmd = ["paper_tables",
                 EXPERIMENTS_DIR / "make_paper_tables.py",
                 "--input-dir", str(out), "--output-dir", str(out / "paper")]
    figures_cmd = ["paper_figures",
                   EXPERIMENTS_DIR / "make_paper_figures.py",
                   "--input-dir", str(out), "--output-dir", str(out / "figures")]
    release_cmd = ["release_check",
                   EXPERIMENTS_DIR / "release_check.py",
                   "--evaluation-status", str(out / "evaluation_status.json")]
    return [
        {"step": s[0], "script": Path(s[1]), "args": s[2:]} for s in
        [_prep(*smoke_cmd), _prep(*build_cmd), _prep(*bench_cmd),
         _prep(*aggregate_cmd), _prep(*paper_cmd), _prep(*figures_cmd),
         _prep(*release_cmd)]
    ]


def _prep(step, script, *args):
    return (step, script, *args)


def plan_script_paths_exist(plan: list[dict]) -> list[str]:
    """Return missing script paths (for dry-run regression tests)."""
    return [str(s["script"]) for s in plan if not Path(s["script"]).exists()]


def run_real_video(video: Path, output_dir: Path, fps: Optional[float], dry_run: bool = False) -> dict:
    if not video.exists():
        raise FileNotFoundError(f"video does not exist: {video}")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    steps = plan_real_video(video, output_dir, fps)
    results = []
    for step in steps:
        if dry_run:
            results.append({"step": step["step"], "status": "DRY_RUN"})
            continue
        cmd = [_PY, str(step["script"])] + [str(a) for a in step["args"]]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            results.append({"step": step["step"], "status": "ok"})
        except Exception:  # noqa: BLE001 - record sanitized failure, continue
            results.append({"step": step["step"], "status": "failed", "error_type": "subprocess"})

    ok_steps = [r for r in results if r["status"] == "ok"]
    failed_steps = [r for r in results if r["status"] == "failed"]
    if dry_run:
        overall = "DRY_RUN"
    elif ok_steps and not failed_steps:
        overall = "COMPLETE"
    elif ok_steps:
        overall = "PARTIAL"
    else:
        overall = "FAILED"

    smoke_ok = False
    bench_ok = False
    smoke_result = _read_json(output_dir / "smoke.json")
    bench_result = _read_json(output_dir / "benchmark_batch.json")
    if not dry_run and smoke_result:
        smoke_ok = smoke_result.get("REAL_RUNTIME_SMOKE") == "COMPLETE"
    if not dry_run and bench_result and isinstance(bench_result, dict):
        bench_ok = bench_result.get("summary", {}).get("REAL_VIDEO_BENCHMARK") == "COMPLETE"
    real_video_runtime = "COMPLETE" if (smoke_ok and bench_ok) else (
        "DRY_RUN" if dry_run else "PENDING"
    )

    # Local evaluation-status refresh (never fabricated).
    local_status = _make_local_status(output_dir, smoke_ok, bench_ok, dry_run)
    atomic_json_write(output_dir / "evaluation_status.json", local_status)

    summary = {
        "orchestrator": "run_real_video_validation",
        "video_present": True,
        "dry_run": dry_run,
        "status": overall,
        "REAL_VIDEO_RUNTIME": real_video_runtime,
        "steps": results,
        "evaluation_status_file": "evaluation_status.json",
    }
    atomic_json_write(output_dir / "real_video_validation.json", summary)
    return summary


def _read_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def _make_local_status(output_dir: Path, smoke_ok: bool, bench_ok: bool, dry_run: bool) -> dict:
    template = _read_json(RESULTS_DIR / "evaluation_status.json") or {"statuses": {}}
    if dry_run:
        template["statuses"]["real_video_smoke"] = "DRY_RUN"
        template["statuses"]["runtime_benchmark_real_video"] = "DRY_RUN"
    else:
        template["statuses"]["real_video_smoke"] = "COMPLETE" if smoke_ok else "PENDING"
        template["statuses"]["runtime_benchmark_real_video"] = "COMPLETE" if bench_ok else "PENDING"
    template["statuses"]["real_video_executed"] = "COMPLETE" if (smoke_ok and bench_ok and not dry_run) else "PENDING"
    return template


def atomic_json_write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="run_real_video_validation", description="Orchestrate real-video validation.")
    p.add_argument("--video", required=True, help="explicit local video path")
    p.add_argument("--output-dir", default=str(RESULTS_DIR / "real_video"))
    p.add_argument("--fps", type=float, default=None)
    p.add_argument("--dry-run", action="store_true", help="print plan without executing")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    result = run_real_video(Path(args.video), Path(args.output_dir), args.fps, args.dry_run)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

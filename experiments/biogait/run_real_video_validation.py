"""Real-video validation orchestrator (Sprint C, C17).

Convenient explicit command path for when a real, non-sensitive test video is
available. Requires explicit ``--video PATH``. It never searches the computer
for videos, never uploads, and never commits the video.

Pipeline (each step optional via flags; dry-run prints the plan):
    smoke -> offline analyze -> benchmark -> aggregate -> paper-table refresh
    -> figure refresh (if matplotlib) -> release-check refresh

Example:
    python experiments/biogait/run_real_video_validation.py --video clip.mp4 --output-dir results/real_video
    python experiments/biogait/run_real_video_validation.py --video clip.mp4 --dry-run
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

from common import RESULTS_DIR, atomic_json_write

_PY = sys.executable
_HERE = Path(__file__).resolve().parent


def plan_real_video(video: Path, output_dir: Path, fps: Optional[float]) -> list[dict]:
    return [
        {"step": "smoke", "cmd": ["smoke_runtime.py", "--video", str(video), "--output", str(output_dir / "smoke.json")]},
        {"step": "offline_analyze", "cmd": ["analyze_video.py", "--input", str(video), "--output", str(output_dir / "session.json")]
         + (["--fps", str(fps)] if fps else [])},
        {"step": "benchmark", "cmd": ["benchmark_video.py", "--input", str(video), "--output", str(output_dir / "benchmark.json")]
         + (["--fps", str(fps)] if fps else [])},
        {"step": "aggregate", "cmd": ["aggregate_results.py", "--output-dir", str(output_dir / "aggregate")]},
        {"step": "paper_tables", "cmd": ["make_paper_tables.py", "--input-dir", str(output_dir), "--output-dir", str(output_dir / "paper")]},
        {"step": "paper_figures", "cmd": ["make_paper_figures.py", "--input-dir", str(output_dir), "--output-dir", str(output_dir / "figures")]},
        {"step": "release_check", "cmd": ["release_check.py"]},
    ]


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
        cmd = [_PY, str(_HERE / step["cmd"][0])] + step["cmd"][1:]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            results.append({"step": step["step"], "status": "ok"})
        except subprocess.CalledProcessError as exc:
            results.append({"step": step["step"], "status": "failed", "error_type": "CalledProcessError"})

    summary = {
        "orchestrator": "run_real_video_validation",
        "video_present": True,
        "dry_run": dry_run,
        "status": "PENDING" if dry_run else "COMPLETE",
        "REAL_VIDEO_RUNTIME": "PENDING" if not video else ("DRY_RUN" if dry_run else "INVOKED"),
        "steps": results,
    }
    atomic_json_write(output_dir / "real_video_validation.json", summary)
    return summary


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="run_real_video_validation", description="Orchestrate real-video validation.")
    p.add_argument("--video", required=True, help="explicit local video path")
    p.add_argument("--output-dir", default=str(RESULTS_DIR / "real_video"))
    p.add_argument("--fps", type=float, default=None)
    p.add_argument("--dry-run", action="store_true", help="print the plan without executing")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    result = run_real_video(Path(args.video), Path(args.output_dir), args.fps, args.dry_run)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

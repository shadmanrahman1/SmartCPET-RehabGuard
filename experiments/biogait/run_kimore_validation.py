"""Real KIMORE validation orchestrator (Sprint C, C18).

Requires an explicit local skeletal file via ``--load PATH`` and ``--fs`` when
the sampling rate cannot be derived from the sequence. It never downloads
KIMORE and never silently assumes a sampling rate.

Pipeline (dry-run support):
    parse -> structural validation -> evaluate Ex5 -> FPS sensitivity (if a
    valid 30-Hz anchor) -> aggregate -> paper-artifact refresh -> status update

Example:
    python experiments/biogait/run_kimore_validation.py --load seq.mat --fs 30 --output-dir results/kimore_ex5
    python experiments/biogait/run_kimore_validation.py --load seq.mat --dry-run
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


def plan_kimore(load_path: Path, output_dir: Path, fs: Optional[float]) -> list[dict]:
    eval_cmd = ["evaluate_kimore_ex5.py", "--load", str(load_path)]
    if fs is not None:
        eval_cmd += ["--fs", str(fs)]
    return [
        {"step": "parse_and_validate", "cmd": ["kimore_adapter.py", "--load", str(load_path)]},
        {"step": "evaluate_ex5", "cmd": eval_cmd},
        {"step": "fps_sensitivity", "cmd": ["fps_sensitivity.py", "--output", str(output_dir / "fps_sensitivity.json")]},
        {"step": "aggregate", "cmd": ["aggregate_results.py", "--output-dir", str(output_dir / "aggregate")]},
        {"step": "paper_tables", "cmd": ["make_paper_tables.py", "--input-dir", str(output_dir), "--output-dir", str(output_dir / "paper")]},
        {"step": "status_update", "cmd": ["kimore_mapping_report.py", "--output-dir", str(output_dir / "mapping")]},
    ]


def run_kimore(load_path: Path, output_dir: Path, fs: Optional[float], dry_run: bool = False) -> dict:
    if not load_path.exists():
        raise FileNotFoundError(f"KIMORE file does not exist: {load_path}")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    steps = plan_kimore(load_path, output_dir, fs)
    results = []
    for step in steps:
        if dry_run:
            results.append({"step": step["step"], "status": "DRY_RUN"})
            continue
        cmd = [_PY, str(_HERE / step["cmd"][0])] + step["cmd"][1:]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            results.append({"step": step["step"], "status": "ok"})
        except subprocess.CalledProcessError:
            results.append({"step": step["step"], "status": "failed", "error_type": "CalledProcessError"})

    summary = {
        "orchestrator": "run_kimore_validation",
        "real_kimore_sequence": True,
        "sampling_rate_required": fs is None,
        "dry_run": dry_run,
        "REAL_KIMORE_VALIDATION": "PENDING" if (fs is None or dry_run) else "INVOKED",
        "steps": results,
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

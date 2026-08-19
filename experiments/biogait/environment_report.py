"""Collect a neutral, reproducible environment report for BioGait.

Captures only non-identifying technical facts:

- Python version, platform (system/release/machine/processor)
- numpy / scipy versions
- opencv (cv2), mediapipe, PyQt5 availability + versions IF installed
- CPU / platform information
- pose-model artifact presence + filename

It deliberately collects NO personal or device identity data:

- NO username
- NO home directory
- NO machine hostname
- NO IP address
- NO private paths
- NO serial numbers

Neutral JSON is only written when explicitly executed with --output (or printed
with --print). This is engineering/reproducibility metadata — it is not a
clinical record and contains no measurements of movement.

Example:
    python experiments/biogait/environment_report.py --output env.json
"""
from __future__ import annotations

import argparse
import importlib
import json
import platform
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BIOGAIT = REPO_ROOT / "biogait"
if str(BIOGAIT) not in sys.path:
    sys.path.insert(0, str(BIOGAIT))

# Pose-model artifact: reported WITHOUT importing analyze_video (which needs
# cv2/mediapipe at import time and would make this report fail headlessly).
MODEL_PATH = BIOGAIT / "pose_landmarker_lite.task"


def _version(module_name: str):
    """Return (available, version) for an optional third-party module."""
    try:
        mod = importlib.import_module(module_name)
    except Exception:
        return False, None
    v = getattr(mod, "__version__", None)
    if v is None:
        v = getattr(getattr(mod, "version", None), "__version__", None)
    return True, (str(v) if v is not None else "unknown")


def collect_environment() -> dict:
    """Return a neutral, non-identifying environment report dict."""
    cv2_avail, cv2_ver = _version("cv2")
    mp_avail, mp_ver = _version("mediapipe")
    pyqt_avail, pyqt_ver = _version("PyQt5")

    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "processor": (platform.processor() or "unknown"),
        },
        "numpy_version": _version("numpy")[1],
        "scipy_version": _version("scipy")[1],
        "opencv_available": cv2_avail,
        "opencv_version": cv2_ver,
        "mediapipe_available": mp_avail,
        "mediapipe_version": mp_ver,
        "PyQt5_available": pyqt_avail,
        "PyQt5_version": pyqt_ver,
        "pose_model_present": MODEL_PATH.exists(),
        "pose_model_filename": MODEL_PATH.name if MODEL_PATH.exists() else None,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="environment_report",
        description="Neutral non-identifying BioGait environment report.",
    )
    parser.add_argument("--output", default=None, help="write neutral JSON to this path")
    parser.add_argument("--print", action="store_true", help="also print JSON to stdout")
    return parser


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    report = collect_environment()
    if args.print or args.output is None:
        print(json.dumps(report, indent=2, allow_nan=False))
    if args.output is not None:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
        print(f"[environment_report] wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

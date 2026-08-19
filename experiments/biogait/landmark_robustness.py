"""Landmark-quality robustness matrix (Sprint B, B9).

Using synthetic FrameEvidence fixtures, evaluates controlled landmark loss /
low visibility and confirms the expected feature-specific degradation. Produces
a compact availability matrix (paper-ready robustness table).

Columns: landmark condition | left PO | right PO | wrist CF | torso CF |
knee CF | overall PO complete.

Conditions: wrist missing, one ankle missing, one knee missing, one hip
missing, both wrists missing, low visibility.

This is deterministic and uses no camera/MediaPipe/hardware. It does not
evaluate MediaPipe accuracy and makes no clinical claim.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Optional

from common import BIOGAIT_DIR, atomic_json_write

if str(BIOGAIT_DIR) not in sys.path:
    sys.path.insert(0, str(BIOGAIT_DIR))

from evidence_features import build_frame_evidence  # noqa: E402


def _lm(x, y, z, visibility=1.0):
    return {"x": x, "y": y, "z": z, "visibility": visibility}


def _default_scene():
    return {
        "left_shoulder": _lm(-0.15, 1.5, 0.0),
        "right_shoulder": _lm(0.15, 1.5, 0.0),
        "left_wrist": _lm(-0.1, 1.4, 0.2),
        "right_wrist": _lm(0.1, 1.4, 0.2),
        "left_hip": _lm(-0.15, 1.0, 0.0),
        "right_hip": _lm(0.15, 1.0, 0.0),
        "left_knee": _lm(-0.15, 0.5, 0.0),
        "right_knee": _lm(0.15, 0.5, 0.0),
        "left_ankle": _lm(-0.15, 0.0, 0.0),
        "right_ankle": _lm(0.15, 0.0, 0.0),
    }


def _condition(name: str) -> dict:
    scene = _default_scene()
    if name == "intact":
        return scene
    if name == "wrist_missing":
        del scene["left_wrist"]
    elif name == "one_ankle_missing":
        del scene["left_ankle"]
    elif name == "one_knee_missing":
        del scene["right_knee"]
    elif name == "one_hip_missing":
        del scene["right_hip"]
    elif name == "both_wrists_missing":
        del scene["left_wrist"]
        del scene["right_wrist"]
    elif name == "low_visibility":
        scene["left_knee"] = _lm(-0.15, 0.5, 0.0, visibility=0.1)
    else:
        raise ValueError(f"unknown condition: {name}")
    return scene


CONDITIONS = (
    "intact",
    "wrist_missing",
    "one_ankle_missing",
    "one_knee_missing",
    "one_hip_missing",
    "both_wrists_missing",
    "low_visibility",
)


def availability_matrix() -> list[dict]:
    rows = []
    for condition in CONDITIONS:
        scene = _condition(condition)
        ev = build_frame_evidence(scene, 0, 0.0)
        q = ev.quality
        cf = ev.control_factors
        rows.append(
            {
                "landmark_condition": condition,
                "left_po": bool(q.get("left_po_available")),
                "right_po": bool(q.get("right_po_available")),
                "wrist_cf": cf.get("wrist_distance_m") is not None
                and cf.get("left_wrist_shoulder_distance_m") is not None,
                "torso_cf": cf.get("torso_area_m2") is not None,
                "knee_cf": cf.get("knee_euclidean_3d_m") is not None,
                "overall_po_complete": bool(q.get("available")),
            }
        )
    return rows


def availability_matrix_csv(rows: list[dict]) -> str:
    import io

    fieldnames = list(rows[0].keys())
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fieldnames)
    w.writeheader()
    for row in rows:
        w.writerow({k: str(v) for k, v in row.items()})
    return buf.getvalue()


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="landmark_robustness",
        description="Feature-specific landmark-loss availability matrix.",
    )
    p.add_argument("--output", default=None, help="JSON output path")
    p.add_argument("--csv", default=None, help="CSV output path")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    import json

    rows = availability_matrix()
    if args.output or args.csv is None:
        print(json.dumps(rows, indent=2, allow_nan=False))
    if args.output:
        atomic_json_write(Path(args.output), rows)
        print(f"[landmark_robustness] wrote {args.output}")
    if args.csv:
        Path(args.csv).write_text(availability_matrix_csv(rows), encoding="utf-8")
        print(f"[landmark_robustness] wrote {args.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

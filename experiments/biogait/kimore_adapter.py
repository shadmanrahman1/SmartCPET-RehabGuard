"""Local-only adapter for the KIMORE dataset (Sprint B, source-data adapter).

This is the SOURCE-DATA adapter. It maps native KIMORE skeletal/joint-position
data into a normalized Python representation used by the evaluation tooling.

IMPORTANT POLICIES:
- Do NOT automatically download the KIMORE dataset.
- Do NOT commit raw KIMORE data.
- Do NOT commit patient/participant-identifying paths.
- Use an explicit root via ``KIMORE_DATASET_ROOT`` or ``--dataset-root``.
- If the real dataset is not locally available, adapter development uses
  synthetic fixtures and reports ``REAL_KIMORE_DATASET_VALIDATION=PENDING``.
  No dataset results are fabricated.

Discovery mode:
    python experiments/biogait/kimore_adapter.py --dataset-root ... --inspect

Normalized representation (one sequence):
    {
      "dataset_group": ..., "dataset_subject_key": ..., "exercise": "ex5_squat",
      "sequence_key": ..., "sampling_rate_hz": ...,
      "joints": {"left_shoulder": {"x": [...], "y": [...], "z": [...]}, ...},
      "timestamps_s": [...] or null
    }

KIMORE joint names are mapped onto BioGait roles by candidate matching
(shoulder / hand / hip / knee / ankle, left & right). The KIMORE paper remains
the primary citation; the wrapper scripts remain implementation evidence.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from pathlib import Path
from typing import Any, Optional

from common import (
    BIOGAIT_DIR,
    atomic_json_write,
    load_json,
    opaque_key,
)

if str(BIOGAIT_DIR) not in sys.path:
    sys.path.insert(0, str(BIOGAIT_DIR))

KIMORE_DATASET_ROOT_ENV = "KIMORE_DATASET_ROOT"

EXERCISE = "ex5_squat"

# BioGait landark role -> candidate KIMORE joint-name fragments.
# Matching is case-insensitive and tolerant of "_" variants.
JOINT_ROLE_CANDIDATES: dict[str, tuple[str, ...]] = {
    "left_shoulder": ("L_SHO", "LEFT_SHOULDER", "LSHO"),
    "right_shoulder": ("R_SHO", "RIGHT_SHOULDER", "RSHO"),
    "left_hand": ("HAND_L", "L_HAND", "LEFT_HAND", "HANDL"),
    "right_hand": ("HAND_R", "R_HAND", "RIGHT_HAND", "HANDR"),
    "left_hip": ("L_HIP", "LEFT_HIP"),
    "right_hip": ("R_HIP", "RIGHT_HIP"),
    "left_knee": ("L_KNEE", "LEFT_KNEE", "LKNEE"),
    "right_knee": ("R_KNEE", "RIGHT_KNEE", "RKNEE"),
    "left_ankle": ("L_ANK", "L_ANKLE", "LEFT_ANKLE"),
    "right_ankle": ("R_ANK", "R_ANKLE", "RIGHT_ANKLE"),
}

REAL_KIMORE_DATASET_VALIDATION = "PENDING"


def _norm(name: str) -> str:
    return name.strip().upper().replace(" ", "_")


def _match_role(col: str) -> Optional[tuple[str, str]]:
    """Return ``(role, axis)`` for a column name, or None if unmatchable."""
    up = _norm(col)
    axis = None
    for suffix in ("_X", "_Y", "_Z", "X", "Y", "Z"):
        if up.endswith(suffix):
            axis = suffix[-1].lower()
            base = up[: -len(suffix)] if suffix.startswith("_") else up[:-1]
            break
    else:
        return None
    for role, candidates in JOINT_ROLE_CANDIDATES.items():
        if base in candidates or any(base.endswith(c) for c in candidates):
            # Avoid partial matches like L_SHOU matching L_SHOULDER.
            if base in candidates:
                return role, axis
    return None


def discover_root(root: Path) -> dict[str, Any]:
    """Inspect a supplied KIMORE root; returns a neutral discovery dict.

    Best-effort: treats depth-1 entries as groups and depth-2 entries as
    subjects, and lists candidate data files. Opaque keys are used; no local
    paths or participant names are exposed.
    """
    root = Path(root).resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"dataset root does not exist or is not a directory: {root}")

    groups: dict[str, dict] = {}
    data_files = []
    for group_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        group_key = opaque_key(str(group_dir.relative_to(root)))
        subjects = []
        for subj_dir in sorted(p for p in group_dir.iterdir() if p.is_dir()):
            subject_key = opaque_key(group_key, subj_dir.name)
            subjects.append(subject_key)
            for f in subj_dir.rglob("*"):
                if f.is_file() and f.suffix.lower() in {".mat", ".csv", ".txt", ".json"}:
                    data_files.append(opaque_key(str(f.relative_to(root))))
        groups[group_key] = {"group_label": group_dir.name, "subjects": subjects}

    return {
        "root_label": root.name,
        "groups": groups,
        "candidate_data_files": sorted(data_files),
        "real_dataset_valid": bool(data_files),
        "validation_status": (
            "REAL_KIMORE_DATASET_VALIDATION=PENDING"
            if not data_files
            else "present"
        ),
        "note": (
            "Real KIMORE validation pending unless candidate data files are "
            "parsed successfully; results are not fabricated."
        ),
    }


def parse_joint_table(filepath: Path) -> Optional[dict[str, dict[str, list[float]]]]:
    """Parse a KIMORE-style joint-position table into role->axes arrays.

    Supports .csv/.txt (header + rows), .json (dict of arrays), and .mat via
    scipy.io (when available). Returns ``None`` when the table cannot be
    mapped to BioGait roles.
    """
    ext = filepath.suffix.lower()
    if ext in {".mat"}:
        try:
            from scipy.io import loadmat
        except Exception:
            return None
        try:
            data = loadmat(str(filepath))
        except Exception:
            return None
        return _map_arrays(data)
    if ext in {".json"}:
        data = load_json(filepath)
        if isinstance(data, dict):
            return _map_arrays(data)
        return None
    if ext in {".csv", ".txt"}:
        return _parse_csv_txt(filepath)
    return None


def _parse_csv_txt(filepath: Path) -> Optional[dict]:
    rows: list[list[str]] = []
    try:
        with open(filepath, newline="", encoding="utf-8", errors="replace") as fh:
            sample = fh.read(4096)
        with open(filepath, newline="", encoding="utf-8", errors="replace") as fh:
            if "," in sample:
                rows = [list(r) for r in csv.reader(fh)]
            else:
                rows = [line.split() for line in fh if line.strip()]
    except Exception:
        return None
    if not rows:
        return None
    header = [h.rstrip("").strip() for h in rows[0]]
    arrays: dict[str, dict[str, list[float]]] = {}
    for row in rows[1:]:
        for col, raw in zip(header, row):
            mapped = _match_role(col)
            if mapped is None:
                continue
            role, axis = mapped
            try:
                value = float(raw)
            except (TypeError, ValueError):
                continue
            arrays.setdefault(role, {"x": [], "y": [], "z": []})[axis].append(value)
    # Only keep roles with full x/y/z coverage for drop analysis.
    return arrays


def _map_arrays(data: dict) -> Optional[dict]:
    arrays: dict[str, dict[str, list[float]]] = {}
    for key, value in data.items():
        if not isinstance(value, (list, tuple)):
            continue
        mapped = _match_role(key)
        if mapped is None:
            continue
        role, axis = mapped
        try:
            floats = [float(v) for v in value]
        except (TypeError, ValueError):
            continue
        arrays.setdefault(role, {"x": [], "y": [], "z": []})[axis].extend(floats)
    return arrays or None


def normalized_ex5_sequence(
    joints: dict[str, dict[str, list[float]]],
    *,
    group: str = "unknown",
    subject_key: str = "unknown",
    sequence_key: str = "unknown",
    sampling_rate_hz: Optional[float] = None,
    timestamps_s: Optional[list[float]] = None,
) -> dict:
    """Wrap parsed joints into a normalized, neutral Ex5 sequence dict."""
    length = min((len(v["x"]) for v in joints.values()), default=0)
    return {
        "dataset_group": group,
        "dataset_subject_key": subject_key,
        "exercise": EXERCISE,
        "sequence_key": sequence_key,
        "n_frames": length,
        "sampling_rate_hz": sampling_rate_hz,
        "joints": joints,
        "timestamps_s": timestamps_s,
    }


def synthetic_ex5_sequence(n_frames: int = 600, fs: float = 30.0, seed: int = 0) -> dict:
    """A deterministic synthetic squat-like KIMORE-joint sequence for tests/dev.

    This is NOT real KIMORE data; it exists so tooling can be developed and
    tested without a licensed dataset. Results computed from it are synthetic
    and must never be presented as real-dataset results.
    """
    def _axes(xs, ys, zs):
        return {"x": xs, "y": ys, "z": zs}

    phase = [2 * math.pi * 0.5 * i / fs for i in range(n_frames)]
    # Sagittal knee flexion: the knee moves forward/back in Z while Y stays
    # fixed, so the source-aligned atan2 knee angle oscillates ~135..225 deg.
    knee_z_l = [0.2 * math.sin(p) for p in phase]
    knee_z_r = [-0.2 * math.sin(p) for p in phase]

    joints = {
        "left_shoulder": _axes([-0.15] * n_frames, [1.4] * n_frames, [0.0] * n_frames),
        "right_shoulder": _axes([0.15] * n_frames, [1.4] * n_frames, [0.0] * n_frames),
        "left_hand": _axes([-0.1] * n_frames, [1.3] * n_frames, [0.2] * n_frames),
        "right_hand": _axes([0.1] * n_frames, [1.3] * n_frames, [0.2] * n_frames),
        "left_hip": _axes([-0.15] * n_frames, [1.0] * n_frames, [0.0] * n_frames),
        "right_hip": _axes([0.15] * n_frames, [1.0] * n_frames, [0.0] * n_frames),
        "left_knee": _axes([-0.15] * n_frames, [0.6] * n_frames, knee_z_l),
        "right_knee": _axes([0.15] * n_frames, [0.6] * n_frames, knee_z_r),
        "left_ankle": _axes([-0.15] * n_frames, [0.0] * n_frames, [0.0] * n_frames),
        "right_ankle": _axes([0.15] * n_frames, [0.0] * n_frames, [0.0] * n_frames),
    }

    return normalized_ex5_sequence(
        joints,
        group="SYNTHETIC",
        subject_key=opaque_key("synthetic", str(seed), "subject"),
        sequence_key=opaque_key("synthetic", str(seed), str(n_frames), str(fs)),
        sampling_rate_hz=fs,
        timestamps_s=[i / fs for i in range(n_frames)],
    )


def _dataset_root(cli_root: Optional[Path]) -> Path:
    env = os.environ.get(KIMORE_DATASET_ROOT_ENV)
    resolved = cli_root or (Path(env) if env else None)
    if resolved is None:
        raise ValueError(
            "no KIMORE dataset root supplied; set KIMORE_DATASET_ROOT or pass "
            "--dataset-root"
        )
    return Path(resolved)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="kimore_adapter",
        description="Local-only KIMORE source-data adapter (inspect / load).",
    )
    p.add_argument("--dataset-root", default=None, help="path to local KIMORE data root")
    p.add_argument("--inspect", action="store_true", help="discover subjects/groups/exercises")
    p.add_argument("--load", default=None, help="parse a single joint-position file")
    p.add_argument("--output", default=None, help="write neutral JSON output")
    p.add_argument("--synthetic", action="store_true", help="emit a synthetic fixture instead of real data")
    p.add_argument("--n-frames", type=int, default=600)
    p.add_argument("--fs", type=float, default=30.0)
    p.add_argument("--seed", type=int, default=0)
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.synthetic:
        seq = synthetic_ex5_sequence(args.n_frames, args.fs, args.seed)
        seq["validation_status"] = "SYNTHETIC_FIXTURE_NOT_REAL_DATA"
        print(json.dumps(seq, indent=2, allow_nan=False))
        if args.output:
            atomic_json_write(Path(args.output), seq)
            print(f"[kimore_adapter] wrote {args.output}")
        return 0

    if args.inspect:
        root = _dataset_root(Path(args.dataset_root) if args.dataset_root else None)
        report = discover_root(root)
        print(json.dumps(report, indent=2, allow_nan=False))
        if args.output:
            atomic_json_write(Path(args.output), report)
            print(f"[kimore_adapter] wrote {args.output}")
        return 0

    if args.load:
        joints = parse_joint_table(Path(args.load))
        if joints is None:
            print("[kimore_adapter] ERROR: could not parse joint data")
            return 1
        seq = normalized_ex5_sequence(joints, sequence_key=opaque_key(args.load))
        seq["validation_status"] = REAL_KIMORE_DATASET_VALIDATION
        print(json.dumps(seq, indent=2, allow_nan=False))
        if args.output:
            atomic_json_write(Path(args.output), seq)
            print(f"[kimore_adapter] wrote {args.output}")
        return 0

    print("[kimore_adapter] no action requested (--inspect, --load, or --synthetic)")
    return 1


if __name__ == "__main__":
    sys.exit(main())

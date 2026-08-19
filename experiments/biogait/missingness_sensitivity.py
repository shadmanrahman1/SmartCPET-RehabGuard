"""Controlled missing-data robustness (Sprint B, B8).

Takes complete valid angle/evidence sequences and injects deterministic
missingness at controlled levels (0, 5, 10, 20, 30%, plus optional burst
dropout) with a fixed seed.

Evaluated: PO availability, reference-path warning behavior, adapted-path
warning behavior, descriptive-feature availability, and rolling-availability
behavior.

IMPORTANT: production analysis is NOT modified to interpolate these gaps. This
experiment measures the robustness/coverage of the current conservative
missing-data behavior. No clinical claims.

Example:
    python experiments/biogait/missingness_sensitivity.py --output missing.json
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path
from typing import Any, Optional

from common import BIOGAIT_DIR, atomic_json_write

if str(BIOGAIT_DIR) not in sys.path:
    sys.path.insert(0, str(BIOGAIT_DIR))

from evidence_features import build_frame_evidence, missing_evidence  # noqa: E402
from reference_temporal import (  # noqa: E402
    kimore_adapted_ex5_temporal_analysis,
    kimore_reference_ex5_temporal_analysis,
)
from session_analysis import SessionAccumulator, descriptive_temporal_features  # noqa: E402

MISSINGNESS_LEVELS = (0.0, 0.05, 0.10, 0.20, 0.30)


def _full_evidence(seq) -> list[dict]:
    from common import to_landmarks

    joints = seq["joints"]
    n = int(seq.get("n_frames", 0))
    fs = seq.get("sampling_rate_hz") or 30.0
    evidence = []
    for i in range(n):
        ts = (seq.get("timestamps_s") or [i / fs for i in range(n)])[i]
        lm = to_landmarks(joints, i)
        evidence.append(build_frame_evidence(lm, i, float(ts)).to_dict())
    return evidence


def _mask_indices(n, level: float, seed: int, burst: bool) -> set[int]:
    rng = random.Random(int(seed * 1000 + round(level * 100)))
    if burst:
        # A single contiguous burst of `level * n` frames.
        length = int(round(level * n))
        start = rng.randint(0, max(0, n - length)) if n else 0
        return set(range(start, start + length))
    indices = list(range(n))
    rng.shuffle(indices)
    k = int(round(level * n))
    return set(indices[:k])


def _apply_missingness(evidence, masked: set[int]) -> list[dict]:
    out = []
    for i, ev in enumerate(evidence):
        if i in masked:
            out.append(missing_evidence(i, ev["timestamp_seconds"]).to_dict())
        else:
            out.append(ev)
    return out


def _left_angle_stream(evidence) -> list[Optional[float]]:
    return [ev["primary_outcomes"]["left_knee_sagittal_deg"] for ev in evidence]


def _rolling_availability(evidence, window=300) -> Optional[float]:
    acc = SessionAccumulator(max_frames=window)
    for ev in evidence:
        acc.add(ev)
    return acc.retained_availability_rate


def _descriptive_feature_availability(evidence) -> float:
    acc = SessionAccumulator()
    for ev in evidence:
        acc.add(ev)
    desc = descriptive_temporal_features(acc.aligned_arrays())
    numeric = [
        desc.get("session_duration_s"),
        desc.get("left_knee_rom_deg"),
        desc.get("right_knee_rom_deg"),
        desc.get("left_peak_abs_angular_velocity_deg_s"),
        desc.get("right_peak_abs_angular_velocity_deg_s"),
    ]
    present = sum(1 for v in numeric if v is not None)
    return present / len(numeric)


def missingness_sensitivity(
    seq,
    levels: tuple[float, ...] = MISSINGNESS_LEVELS,
    seed: int = 0,
    burst: bool = False,
) -> dict:
    full = _full_evidence(seq)
    n = len(full)
    rows = []
    for level in levels:
        masked = _mask_indices(n, level, seed, burst)
        evidence = _apply_missingness(full, masked)
        left_angles = _left_angle_stream(evidence)
        fs = seq.get("sampling_rate_hz") or 30.0
        ts = seq.get("timestamps_s") or [i / fs for i in range(n)]
        ref = kimore_reference_ex5_temporal_analysis(left_angles, ts, fs)
        adapted = kimore_adapted_ex5_temporal_analysis(left_angles, ts, fs)

        po_both = sum(1 for ev in evidence if ev["quality"].get("available"))
        po_left = sum(1 for ev in evidence if ev["quality"].get("left_po_available"))
        po_right = sum(1 for ev in evidence if ev["quality"].get("right_po_available"))

        rows.append(
            {
                "missingness_level": level,
                "missing_frames": len(masked),
                "total_frames": n,
                "po_coverage": {
                    "left": round(po_left / n, 4),
                    "right": round(po_right / n, 4),
                    "both": round(po_both / n, 4),
                },
                "reference_path_status": (
                    "runs"
                    if ref.get("warning") is None
                    else f"warning:{ref.get('warning')}"
                ),
                "adapted_path_status": (
                    "runs"
                    if adapted.get("warning") is None
                    else f"warning:{adapted.get('warning')}"
                ),
                "descriptive_feature_availability_fraction": round(
                    _descriptive_feature_availability(evidence), 4
                ),
                "rolling_availability_rate": round(
                    _rolling_availability(evidence), 4
                ),
            }
        )
    return {
        "experiment": "missingness_sensitivity",
        "schema_version": "1.0",
        "seed": int(seed),
        "burst_dropout": bool(burst),
        "note": (
            "Measures robust coverage of the current conservative missing-data "
            "behavior; production analysis is not modified to interpolate gaps."
        ),
        "rows": rows,
    }


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="missingness_sensitivity",
        description="Controlled missing-data robustness experiment.",
    )
    p.add_argument("--output", default=None, help="JSON output path")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--burst", action="store_true", help="use a contiguous burst instead of uniform missingness")
    p.add_argument("--n-frames", type=int, default=900)
    p.add_argument("--print", action="store_true", help="print result JSON")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    import json

    from kimore_adapter import synthetic_ex5_sequence

    seq = synthetic_ex5_sequence(args.n_frames, 30.0, seed=args.seed)
    result = missingness_sensitivity(seq, seed=args.seed, burst=args.burst)
    if args.print or args.output is None:
        print(json.dumps(result, indent=2, allow_nan=False))
    if args.output:
        atomic_json_write(Path(args.output), result)
        print(f"[missingness_sensitivity] wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

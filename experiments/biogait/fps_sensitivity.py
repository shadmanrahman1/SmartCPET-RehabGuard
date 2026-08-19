"""Sampling-rate sensitivity experiment (Sprint B, B7).

Evaluates the effect of controlled sampling-rate transformations on the
source-aligned kinematic + adapted temporal descriptors for a complete angle
sequence (preferably a KIMORE Ex5 source sequence).

Rates evaluated: 15, 20, 24, 25, 29.97, 30, 50, 60 Hz.

Provenance:
- The 30 Hz source-aligned reference result remains the REFERENCE_DERIVED anchor.
- All other rates are ENGINEERING_ADAPTED sensitivity experiments.
- Resampling is used ONLY in this experiment layer (never added silently to the
  production reference function).

Recorded: ROM drift, peak/mean angular-velocity drift, candidate-event-count
differences. MAE/RMSE are reported only when mathematically well-defined and
aligned as scalar drift metrics. This is NOT clinical accuracy.

Example:
    python experiments/biogait/fps_sensitivity.py --output sensitivity.json
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Any, Optional, Sequence

import numpy as np

from common import BIOGAIT_DIR, atomic_json_write, opaque_key

if str(BIOGAIT_DIR) not in sys.path:
    sys.path.insert(0, str(BIOGAIT_DIR))

from reference_temporal import (  # noqa: E402
    kimore_adapted_ex5_temporal_analysis,
    kimore_reference_ex5_temporal_analysis,
)

DEFAULT_RATES = (15.0, 20.0, 24.0, 25.0, 29.97, 30.0, 50.0, 60.0)


def resample_uniform(
    values: Sequence[float],
    src_fs: float,
    dst_fs: float,
) -> list[float]:
    """Deterministically resample a uniformly sampled sequence to ``dst_fs``.

    Uses linear interpolation onto a uniform time grid that preserves physical
    duration. This is an EXPERIMENT-layer helper; it is never added to the
    production reference function.
    """
    src = np.asarray([float(v) for v in values], dtype=float)
    n = len(src)
    if n < 2:
        return list(src)
    duration = (n - 1) / src_fs
    n_dst = int(round(duration * dst_fs)) + 1
    n_dst = max(1, n_dst)
    t_src = np.arange(n) / src_fs
    t_dst = np.arange(n_dst) / dst_fs
    return [float(v) for v in np.interp(t_dst, t_src, src)]


def _abs_stats_deg_s(values: list[float], dt: float) -> tuple[Optional[float], Optional[float]]:
    omegas = [
        (b - a) / dt for a, b in zip(values, values[1:]) if math.isfinite(a) and math.isfinite(b)
    ]
    if not omegas:
        return None, None
    absv = [abs(o) for o in omegas]
    return max(absv), sum(absv) / len(absv)


def _rom(values: Sequence[float]) -> Optional[float]:
    finite = [v for v in values if math.isfinite(v)]
    if len(finite) < 2:
        return None
    return max(finite) - min(finite)


def angle_sequence_from_knee(joints: dict, role: str) -> list[float]:
    """Derive a left/right knee-angle stream from KIMORE-style joints."""
    from common import to_landmarks
    from evidence_features import kimore_reference_sagittal_knee_angle_yz

    n = len(joints[role]["x"])
    out = []
    for i in range(n):
        lm = to_landmarks(joints, i)
        if role == "left_knee":
            hip, knee, ankle = lm.get("left_hip"), lm.get("left_knee"), lm.get("left_ankle")
        else:
            hip, knee, ankle = lm.get("right_hip"), lm.get("right_knee"), lm.get("right_ankle")
        out.append(kimore_reference_sagittal_knee_angle_yz(hip, knee, ankle))
    return out


def _anchor_result(angles, anchor_fs, side) -> dict:
    timestamps = [i / anchor_fs for i in range(len(angles))]
    ref = kimore_reference_ex5_temporal_analysis(angles, timestamps, anchor_fs)
    adapted = kimore_adapted_ex5_temporal_analysis(angles, timestamps, anchor_fs)
    dt = 1.0 / anchor_fs
    peak, mean = _abs_stats_deg_s([a for a in angles if a is not None], dt)
    return {
        "side": side,
        "fps": anchor_fs,
        "classification": "REFERENCE_DERIVED",
        "rom_deg": round(_rom(angles), 4) if _rom(angles) is not None else None,
        "peak_abs_angular_velocity_deg_s": round(peak, 4) if peak is not None else None,
        "mean_abs_angular_velocity_deg_s": round(mean, 4) if mean is not None else None,
        "n_event_candidates": len(ref.get("maxima_indices", [])),
        "reference_warning": ref.get("warning"),
        "adapted_warning": adapted.get("warning"),
    }


def _rate_result(angles, src_fs, rate, side, anchor) -> dict:
    resampled = resample_uniform(angles, src_fs, rate)
    timestamps = [i / rate for i in range(len(resampled))]
    adapted = kimore_adapted_ex5_temporal_analysis(resampled, timestamps, rate)
    dt = 1.0 / rate
    peak, mean = _abs_stats_deg_s([a for a in resampled if a is not None], dt)
    rom = _rom(resampled)
    n_events = len(adapted.get("maxima_indices", []))
    return {
        "side": side,
        "fps": round(rate, 4),
        "classification": "ENGINEERING_ADAPTED",
        "rom_deg": round(rom, 4) if rom is not None else None,
        "peak_abs_angular_velocity_deg_s": round(peak, 4) if peak is not None else None,
        "mean_abs_angular_velocity_deg_s": round(mean, 4) if mean is not None else None,
        "n_event_candidates": n_events,
        "adapted_warning": adapted.get("warning"),
        "drift_vs_30hz": {
            "rom_drift_abs": (
                round(abs(rom - anchor["rom_deg"]), 4)
                if rom is not None and anchor["rom_deg"] is not None
                else None
            ),
            "peak_angvel_drift_abs": (
                round(abs(peak - anchor["peak_abs_angular_velocity_deg_s"]), 4)
                if peak is not None and anchor["peak_abs_angular_velocity_deg_s"] is not None
                else None
            ),
            "event_count_diff": (
                n_events - anchor["n_event_candidates"]
            ),
        },
        "note": "Engineering sensitivity experiment; not clinical accuracy.",
    }


def fps_sensitivity(
    left_angles: list[float],
    right_angles: list[float],
    src_fs: float = 30.0,
    rates: Sequence[float] = DEFAULT_RATES,
    data_origin: str = "UNKNOWN_UNVALIDATED",
) -> dict:
    if not math.isclose(src_fs, 30.0, rel_tol=0.0, abs_tol=1e-6):
        raise ValueError("fps_sensitivity expects a 30 Hz source sequence as the REFERENCE anchor")
    anchor_left = _anchor_result(left_angles, src_fs, "left")
    anchor_right = _anchor_result(right_angles, src_fs, "right")
    left_rows = [_anchor_result(left_angles, src_fs, "left")]
    right_rows = [_anchor_result(right_angles, src_fs, "right")]
    for rate in rates:
        if math.isclose(rate, 30.0, rel_tol=0.0, abs_tol=1e-6):
            continue
        left_rows.append(_rate_result(left_angles, src_fs, rate, "left", anchor_left))
        right_rows.append(_rate_result(right_angles, src_fs, rate, "right", anchor_right))
    for row in left_rows + right_rows:
        row["data_origin"] = data_origin
    return {
        "experiment": "fps_sensitivity",
        "schema_version": "1.0",
        "data_origin": data_origin,
        "source_fs": src_fs,
        "rates_evaluated": [round(r, 4) for r in [30.0] + [r for r in rates if not math.isclose(r, 30.0, abs_tol=1e-6)]],
        "note": (
            "30 Hz is the REFERENCE_DERIVED anchor (method provenance) for "
            "non-30 Hz ENGINEERING_ADAPTED experiments. data_origin describes "
            "the input source and is distinct from method provenance; a "
            "synthetic 30 Hz fixture is NOT real-dataset evidence."
        ),
        "rows": left_rows + right_rows,
    }


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="fps_sensitivity",
        description="Sampling-rate sensitivity experiment for the source-aligned kinematics.",
    )
    p.add_argument("--output", default=None, help="JSON output path")
    p.add_argument("--n-frames", type=int, default=600)
    p.add_argument("--sequence-json", default=None,
                   help="run on a REAL normalized KIMORE sequence (derives knee-angle streams)")
    p.add_argument("--print", action="store_true", help="print result JSON")
    return p


def _status_result(status: str, output: Optional[Path], note: str) -> dict:
    result = {
        "experiment": "fps_sensitivity",
        "schema_version": "1.0",
        "status": status,
        "note": note,
        "rows": [],
    }
    if output is not None:
        atomic_json_write(output, result)
        print(f"[fps_sensitivity] wrote {output}")
    return result


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    import json

    if args.sequence_json:
        from common import load_json
        seq = load_json(Path(args.sequence_json))
        if not isinstance(seq, dict) or not seq.get("joints"):
            result = _status_result("PENDING_VALID_30HZ_ANCHOR", Path(args.output) if args.output else None,
                                    "sequence-json is not a normalized {joints:...} object")
            print(json.dumps(result, indent=2, allow_nan=False))
            return 1 if False else 0
        fs = seq.get("sampling_rate_hz")
        if not isinstance(fs, (int, float)) or not math.isclose(float(fs), 30.0, rel_tol=0.0, abs_tol=1e-6):
            result = _status_result(
                "PENDING_VALID_30HZ_ANCHOR",
                Path(args.output) if args.output else None,
                "A valid 30 Hz anchor is required for reference-aligned FPS "
                "sensitivity; a non-30 Hz source is not resampled into a fake "
                "REFERENCE_DERIVED anchor.",
            )
            print(json.dumps(result, indent=2, allow_nan=False))
            return 0
        left = angle_sequence_from_knee(seq["joints"], "left_knee")
        right = angle_sequence_from_knee(seq["joints"], "right_knee")
        origin = "UNKNOWN_UNVALIDATED"
        raw_origin = str(seq.get("data_origin", ""))
        if raw_origin.startswith("REAL_"):
            origin = "REAL_KIMORE_NATIVE_SKELETON"
        elif raw_origin == "SYNTHETIC_FIXTURE":
            origin = "SYNTHETIC_FIXTURE"
        result = fps_sensitivity(left, right, src_fs=30.0, data_origin=origin)
        if args.print or args.output is None:
            print(json.dumps(result, indent=2, allow_nan=False))
        if args.output:
            atomic_json_write(Path(args.output), result)
            print(f"[fps_sensitivity] wrote {args.output}")
        return 0

    from kimore_adapter import synthetic_ex5_sequence

    seq = synthetic_ex5_sequence(args.n_frames, 30.0, seed=0)
    left = angle_sequence_from_knee(seq["joints"], "left_knee")
    right = angle_sequence_from_knee(seq["joints"], "right_knee")
    result = fps_sensitivity(
        left, right, src_fs=30.0, data_origin="SYNTHETIC_FIXTURE"
    )
    if args.print or args.output is None:
        print(json.dumps(result, indent=2, allow_nan=False))
    if args.output:
        atomic_json_write(Path(args.output), result)
        print(f"[fps_sensitivity] wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

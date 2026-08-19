"""Direct KIMORE Ex5 source-skeleton evaluator (Sprint B, B5).

Evaluates the Python SOURCE-ALIGNED kinematic implementation directly on
KIMORE skeletal/joint coordinates. This does NOT evaluate MediaPipe accuracy —
it checks that the Python re-implementation of the reviewed KIMORE Ex5
geometry + temporal reference path runs on the native skeleton representation.

Pipeline, per sequence:
    KIMORE skeletal joint positions
        -> KIMORE joint mapping (kimore_adapter)
        -> source-aligned sagittal knee PO (evidence_features)
        -> source-aligned CF geometry (evidence_features)
        -> source-aligned temporal reference path when prerequisites hold
        -> descriptive summary JSON/CSV

Collected (neutral opaque keys only): subject/sequence key, group label,
n_frames, sampling rate, missing-data rate, left/right PO coverage, CF
coverage, left/right ROM, event-candidate counts per side, filter/reference
warning status.

This never produces: clinical correctness, a diagnosis, rehabilitation quality,
good/bad labels, or cPO/cCF/cTS prediction.

Example:
    python experiments/biogait/evaluate_kimore_ex5.py --manifest file.json --output-dir out
    python experiments/biogait/evaluate_kimore_ex5.py --synthetic --n-frames 600 --fs 30 --output-dir out
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Iterable, Optional

from common import (
    BIOGAIT_DIR,
    RESULTS_DIR,
    atomic_json_write,
    load_json,
    opaque_key,
    to_landmarks,
)

if str(BIOGAIT_DIR) not in sys.path:
    sys.path.insert(0, str(BIOGAIT_DIR))

from evidence_features import (  # noqa: E402
    build_frame_evidence,
    compute_control_factors,
)
from reference_temporal import (  # noqa: E402
    kimore_adapted_ex5_temporal_analysis,
    kimore_reference_ex5_temporal_analysis,
)
from kimore_adapter import (  # noqa: E402
    EXERCISE,
    normalized_ex5_sequence,
    parse_joint_table,
    synthetic_ex5_sequence,
)

CONTROL_FACTOR_COVERAGE_KEYS = (
    "wrist_distance_m",
    "shoulder_distance_m",
    "hip_distance_m",
    "knee_euclidean_3d_m",
    "ankle_distance_m",
    "torso_area_m2",
)


def _range_deg(values: list[Optional[float]]) -> Optional[float]:
    finite = [v for v in values if v is not None and math.isfinite(v)]
    if len(finite) < 2:
        return None
    return max(finite) - min(finite)


def _per_side_summary(analysis: dict) -> dict:
    return {
        "classification": analysis.get("classification"),
        "warning": analysis.get("warning"),
        "n_event_candidates": len(analysis.get("maxima_indices", [])),
        "filtered_length": len(analysis.get("filtered_signal", [])),
    }


def _valid_fs(value) -> Optional[float]:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) and f > 0 else None


def _resolve_timestamps(seq, n_frames: int, fs: Optional[float]):
    """Return ``(timestamps, issue)``. Never silently replaces malformed data."""
    raw = seq.get("timestamps_s")
    if raw is not None:
        values = list(raw)
        if len(values) != n_frames:
            return None, "timestamps_length_mismatch"
        ts = []
        for v in values:
            try:
                f = float(v)
            except (TypeError, ValueError):
                return None, "invalid_timestamps"
            if not math.isfinite(f):
                return None, "invalid_timestamps"
            ts.append(f)
        return ts, None
    if fs is not None:
        return [i / fs for i in range(n_frames)], None
    return None, None


def evaluate_sequence(
    seq: dict,
    fs_override: Optional[float] = None,
    data_origin: Optional[str] = None,
) -> dict:
    """Evaluate one normalized KIMORE sequence; returns a neutral result dict.

    Sampling-rate policy: for real/unknown data the rate must come from the
    sequence itself or an explicit caller override. There is NO silent 30 Hz
    fallback — without a valid rate, temporal filtering is NOT run and a
    structured ``sampling_rate_status`` is reported; geometry/coverage may
    still be calculated when joint frames exist.

    ``data_origin`` is kept distinct from methodology provenance. It is taken
    from the caller, else from ``seq["data_origin"]``, else
    ``UNKNOWN_UNVALIDATED``.
    """
    joints = seq.get("joints", {}) or {}
    n_frames = min((len(v.get("x", [])) for v in joints.values()), default=0)

    fs = _valid_fs(seq.get("sampling_rate_hz"))
    if fs is None:
        fs = _valid_fs(fs_override)

    timestamps_s, ts_issue = _resolve_timestamps(seq, n_frames, fs)
    if ts_issue is not None:
        # Malformed supplied timestamps: never silently replace them.
        return {
            "schema_version": "1.0",
            "exercise": seq.get("exercise", EXERCISE),
            "dataset_group": seq.get("dataset_group"),
            "dataset_subject_key": seq.get("dataset_subject_key"),
            "sequence_key": seq.get("sequence_key"),
            "data_origin": data_origin or seq.get("data_origin") or "UNKNOWN_UNVALIDATED",
            "n_frames": n_frames,
            "sampling_rate_hz": round(fs, 4) if fs is not None else None,
            "sampling_rate_status": (
                "ok" if fs is not None
                else "sampling_rate_required_for_temporal_analysis"
            ),
            "evaluation_status": f"invalid_timestamps:{ts_issue}",
            "temporal_analysis": None,
        }

    left_angles: list[Optional[float]] = []
    right_angles: list[Optional[float]] = []
    left_po_ok = 0
    right_po_ok = 0
    available_frames = 0
    cf_counts: dict[str, int] = {k: 0 for k in CONTROL_FACTOR_COVERAGE_KEYS}

    for i in range(n_frames):
        ts = float(timestamps_s[i]) if timestamps_s is not None else float(i)
        lm = to_landmarks(joints, i)
        evidence = build_frame_evidence(lm, i, ts)
        q = evidence.quality
        if q.get("left_po_available"):
            left_po_ok += 1
        if q.get("right_po_available"):
            right_po_ok += 1
        if q.get("available"):
            available_frames += 1
        left_angles.append(evidence.primary_outcomes["left_knee_sagittal_deg"])
        right_angles.append(evidence.primary_outcomes["right_knee_sagittal_deg"])
        cf = evidence.control_factors
        for key in cf_counts:
            if cf.get(key) is not None:
                cf_counts[key] += 1

    missing_data_rate = (
        (n_frames - available_frames) / n_frames if n_frames else None
    )

    if fs is None:
        sampling_rate_status = "sampling_rate_required_for_temporal_analysis"
        temporal_analysis = None
    else:
        sampling_rate_status = "ok"
        ref_left = kimore_reference_ex5_temporal_analysis(left_angles, timestamps_s, fs)
        ref_right = kimore_reference_ex5_temporal_analysis(right_angles, timestamps_s, fs)
        adapted_left = kimore_adapted_ex5_temporal_analysis(left_angles, timestamps_s, fs)
        adapted_right = kimore_adapted_ex5_temporal_analysis(right_angles, timestamps_s, fs)
        temporal_analysis = {
            "reference": {
                "classification": "REFERENCE_DERIVED",
                "left": _per_side_summary(ref_left),
                "right": _per_side_summary(ref_right),
            },
            "adapted": {
                "classification": "ENGINEERING_ADAPTED",
                "left": _per_side_summary(adapted_left),
                "right": _per_side_summary(adapted_right),
            },
        }

    return {
        "schema_version": "1.0",
        "exercise": seq.get("exercise", EXERCISE),
        "dataset_group": seq.get("dataset_group"),
        "dataset_subject_key": seq.get("dataset_subject_key"),
        "sequence_key": seq.get("sequence_key"),
        "data_origin": data_origin or seq.get("data_origin") or "UNKNOWN_UNVALIDATED",
        "execution_status": "COMPLETE" if n_frames else "NO_JOINT_FRAMES",
        "sampling_rate_hz": round(fs, 4) if fs is not None else None,
        "sampling_rate_status": sampling_rate_status,
        "n_frames": n_frames,
        "missing_data_rate_frames": (
            round(missing_data_rate, 4) if missing_data_rate is not None else None
        ),
        "po_coverage": {
            "left": round(left_po_ok / n_frames, 4) if n_frames else None,
            "right": round(right_po_ok / n_frames, 4) if n_frames else None,
            "both": round(available_frames / n_frames, 4) if n_frames else None,
        },
        "control_factor_coverage": {
            key: round(count / n_frames, 4) if n_frames else None
            for key, count in cf_counts.items()
        },
        "descriptive": {
            "left_knee_rom_deg": (
                round(_range_deg(left_angles), 4)
                if _range_deg(left_angles) is not None
                else None
            ),
            "right_knee_rom_deg": (
                round(_range_deg(right_angles), 4)
                if _range_deg(right_angles) is not None
                else None
            ),
        },
        "temporal_analysis": temporal_analysis,
        "note": (
            "data_origin describes the input source; method provenance "
            "(REFERENCE_DERIVED / ENGINEERING_ADAPTED) describes the method. "
            "REFERENCE_DERIVED never implies real KIMORE data."
        ),
    }


def evaluate_sequences(
    sequences: Iterable[dict],
    *,
    fs_override: Optional[float] = None,
    data_origin: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[dict]:
    results = []
    for seq in sequences:
        results.append(
            evaluate_sequence(seq, fs_override=fs_override, data_origin=data_origin)
        )
        if limit and len(results) >= limit:
            break
    return results


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="evaluate_kimore_ex5",
        description="Evaluate the source-aligned Python KIMORE Ex5 implementation on native skeleton data.",
    )
    p.add_argument("--synthetic", action="store_true",
                   help="evaluate a deterministic synthetic Ex5 fixture (data_origin=SYNTHETIC_FIXTURE)")
    p.add_argument("--load", default=None,
                   help="evaluate one explicit local skeletal file via kimore_adapter.parse_joint_table")
    p.add_argument("--sequence-json", default=None,
                   help="evaluate a normalized adapter output (JSON with 'joints')")
    p.add_argument("--manifest", default=None,
                   help="evaluate sequences from a JSON list of {joints,...} (NOT a metadata-only manifest)")
    p.add_argument("--fs", type=float, default=None,
                   help="explicit sampling-rate override (required for real data without a sequence rate)")
    p.add_argument("--n-frames", type=int, default=600)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--output", default=None, help="evaluation results JSON (one per sequence)")
    p.add_argument("--output-dir", default=None, help="write one JSON per sequence + aggregate index")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)

    results: list[dict] = []
    if args.synthetic:
        seq = synthetic_ex5_sequence(args.n_frames, args.fs or 30.0, args.seed)
        results = [evaluate_sequence(seq, fs_override=args.fs, data_origin="SYNTHETIC_FIXTURE")]
    elif args.load:
        joints = parse_joint_table(Path(args.load))
        if joints is None:
            print("[evaluate_kimore_ex5] ERROR: could not parse the supplied skeletal file")
            return 1
        seq = normalized_ex5_sequence(
            joints,
            group="REAL_KIMORE",
            subject_key=opaque_key(args.load),
            sequence_key=opaque_key(args.load),
            sampling_rate_hz=args.fs,  # explicit if supplied; else None -> temporal requires fs
        )
        results = [evaluate_sequence(seq, fs_override=args.fs, data_origin="REAL_KIMORE_NATIVE_SKELETON")]
    elif args.sequence_json:
        seq = load_json(Path(args.sequence_json))
        if not isinstance(seq, dict) or not seq.get("joints"):
            print("[evaluate_kimore_ex5] ERROR: sequence-json must be a normalized {joints:...} object")
            return 1
        origin = ("REAL_KIMORE_NATIVE_SKELETON"
                  if str(seq.get("data_origin", "")).startswith("REAL_")
                  else "UNKNOWN_UNVALIDATED")
        results = [evaluate_sequence(seq, fs_override=args.fs, data_origin=origin)]
    elif args.manifest:
        data = load_json(Path(args.manifest))
        if data is None:
            print("[evaluate_kimore_ex5] ERROR: manifest not found")
            return 1
        sequences = data.get("entries", data) if isinstance(data, dict) else data
        if isinstance(sequences, dict):
            sequences = [sequences]
        if not sequences or not all(isinstance(s, dict) and s.get("joints") for s in sequences):
            print(
                "[evaluate_kimore_ex5] ERROR: manifest_contains_metadata_only_no_sequence_payload "
                "(no 'joints' payload found); provide --load or --sequence-json"
            )
            return 1
        origin = ("REAL_KIMORE_NATIVE_SKELETON"
                  if any(str(s.get("data_origin", "")).startswith("REAL_") for s in sequences)
                  else "UNKNOWN_UNVALIDATED")
        results = evaluate_sequences(sequences, fs_override=args.fs, data_origin=origin, limit=args.limit)
    else:
        print("[evaluate_kimore_ex5] provide --synthetic, --load, --sequence-json, or --manifest")
        return 1

    if args.output_dir:
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        index = []
        for res in results:
            name = opaque_key("ex5", str(res.get("dataset_subject_key")), str(res.get("sequence_key"))) + ".json"
            atomic_json_write(out_dir / name, res)
            index.append({"sequence_key": res.get("sequence_key"), "file": name})
        atomic_json_write(out_dir / "_index.json", {"results": index})
        print(f"[evaluate_kimore_ex5] wrote {len(results)} results to {out_dir}")
        print(json.dumps(index, indent=2, allow_nan=False))
    else:
        print(json.dumps(results, indent=2, allow_nan=False))

    if args.output:
        atomic_json_write(Path(args.output), results if len(results) > 1 else results[0])
    return 0


if __name__ == "__main__":
    sys.exit(main())

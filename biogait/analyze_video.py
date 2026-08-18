"""BioGait offline video analyzer (M4, Sprint A).

Reproducible experiment path: processes a video frame-by-frame with the same
MediaPipe PoseLandmarker model, extracts world-landmark research evidence,
accumulates a session, runs the offline KIMORE reference temporal analysis,
and writes a structured, versioned session JSON.

No Qt GUI is required. A live webcam is NOT required.

Example:
    python biogait/analyze_video.py ^
        --input path/to/video.mp4 ^
        --output path/to/session.json

IMPORTANT: this is an OFFLINE research/experiment path. Results are
descriptive and reference-derived; they are not a clinical assessment.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Optional

import cv2

# MediaPipe is imported lazily below because it is a heavy runtime dependency
# not required to *parse* this module (kept importable in lightweight CI).
from metrics import add_session_fields, calculate_pose_metrics, no_pose_metrics
from runtime_utils import MonotonicClock
from evidence_features import (
    build_frame_evidence,
    extract_normalized_landmarks,
    extract_world_landmarks,
)
from reference_temporal import (
    kimore_reference_ex5_temporal_analysis,
    merge_side_events,
)
from session_analysis import (
    SessionAccumulator,
    build_session_export,
    descriptive_temporal_features,
)

MODEL_PATH = Path(__file__).resolve().parent / "pose_landmarker_lite.task"
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task"
)

METHOD_PROVENANCE = {
    "primary_outcomes": {
        "classification": "ENGINEERING_ADAPTED",
        "reference": "Capecci et al. 2019 (KIMORE), IEEE TNSRE",
        "doi": "10.1109/TNSRE.2019.2923060",
        "note": "KIMORE sagittal knee geometry adapted to MediaPipe world "
                "landmarks inferred from monocular RGB.",
    },
    "control_factors": {
        "classification": "ENGINEERING_ADAPTED",
        "wrist_proxy": (
            "MediaPipe wrist used as an ENGINEERING_ADAPTED proxy for the "
            "KIMORE Hand joint; not an exact kinematic equivalent."
        ),
    },
    "filtering": {
        "reference": "kimore_reference_zero_phase_filter (ref filter, offline, "
                     "non-causal; order 3, 1 Hz, 30 Hz reference sample rate)",
        "causal": "CausalKimoreButterworth is an engineering adaptation with "
                  "phase delay and no clinical validation; not used here.",
    },
    "temporal_analysis": {
        "classification": "REFERENCE_DERIVED",
        "offline": True,
        "note": "Reference peak settings are not automatically valid for an "
                "arbitrary live session length.",
    },
}

LIMITATIONS = [
    "BioGait is KIMORE-informed rather than a direct KIMORE reproduction. "
    "KIMORE uses Kinect-derived 3D skeletal measurements, whereas BioGait "
    "uses MediaPipe world landmarks inferred from monocular RGB. Numerical "
    "equivalence and clinical validity are not assumed.",
    "The offline reference temporal analysis is non-causal (filtfilt) and "
    "must not be used as realtime causal filtering.",
    "Reference full-sequence peak settings are not automatically valid for "
    "an arbitrary session length; detected events are candidates, not "
    "clinically valid repetitions.",
    "Descriptive ROM / angular velocity values are kinematic summaries only; "
    "they are not clinical scores, pass/fail, or rehabilitation-quality "
    "judgements.",
    "MediaPipe wrist is a proxy for the KIMORE Hand joint; distances involving "
    "the wrist are engineering-adapted proxies.",
    "This output contains no personal identifiers; it should not be "
    "correlated to participant identity outside of a consented research "
    "protocol.",
]


def _ensure_model() -> str:
    if not MODEL_PATH.exists():
        print(f"[analyze_video] Downloading pose model to {MODEL_PATH}")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    return str(MODEL_PATH)


def _build_landmarker(model_path: str):
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision as mp_vision

    base_opts = mp_python.BaseOptions(model_asset_path=model_path)
    opts = mp_vision.PoseLandmarkerOptions(
        base_options=base_opts,
        running_mode=mp_vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    return mp_vision.PoseLandmarker.create_from_options(opts)


def _open_video(path) -> tuple[Any, float, bool]:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"could not open video: {path}")
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    fps_ok = not (fps <= 0 or fps != fps)  # false when 0 or NaN
    return cap, (fps if fps_ok else 30.0), fps_ok


def _write_csv(path: Path, frames: list[dict]) -> None:
    fieldnames = [
        "frame_index",
        "timestamp_s",
        "available",
        "left_knee_sagittal_deg",
        "right_knee_sagittal_deg",
        "wrist_distance_m",
        "shoulder_distance_m",
        "hip_distance_m",
        "knee_distance_m",
        "ankle_distance_m",
        "torso_area_m2",
    ]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for frame in frames:
            q = frame["quality"]
            po = frame["primary_outcomes"]
            cf = frame["control_factors"]
            writer.writerow(
                {
                    "frame_index": frame["frame_index"],
                    "timestamp_s": frame["timestamp_seconds"],
                    "available": q.get("available"),
                    "left_knee_sagittal_deg": po["left_knee_sagittal_deg"],
                    "right_knee_sagittal_deg": po["right_knee_sagittal_deg"],
                    "wrist_distance_m": cf.get("wrist_distance_m"),
                    "shoulder_distance_m": cf.get("shoulder_distance_m"),
                    "hip_distance_m": cf.get("hip_distance_m"),
                    "knee_distance_m": cf.get("knee_distance_m"),
                    "ankle_distance_m": cf.get("ankle_distance_m"),
                    "torso_area_m2": cf.get("torso_area_m2"),
                }
            )


def analyze_video(
    input_path: Path,
    output_path: Path,
    *,
    model_path: Optional[Path] = None,
    fps_override: Optional[float] = None,
    max_frames: int = 0,
    csv_path: Optional[Path] = None,
    include_legacy: bool = False,
) -> dict:
    """Run the offline analysis and write the structured session JSON."""
    mp = __import__("mediapipe")
    cap, video_fps, fps_from_video = _open_video(input_path)
    fps = float(fps_override) if fps_override else video_fps

    model = _ensure_model() if model_path is None else str(model_path)
    landmarker = _build_landmarker(model)

    accumulator = SessionAccumulator(max_frames=max_frames if max_frames > 0 else None)
    frames: list[dict] = []
    clock = MonotonicClock()
    legacy_frames_read = 0
    start_wall = time.perf_counter()

    try:
        with landmarker:
            frame_index = 0
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                timestamp_s = (
                    float(frame_index) / fps if fps_from_video or fps_override
                    else clock.elapsed_seconds()
                )
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                result = landmarker.detect_for_video(
                    img, clock.video_timestamp_ms()
                )

                world = extract_world_landmarks(result)
                evidence = build_frame_evidence(
                    world, frame_index, timestamp_s
                ).to_dict()

                if include_legacy:
                    legacy_frames_read += 1
                    lms = extract_normalized_landmarks(result)
                    if lms:
                        metrics = calculate_pose_metrics(lms)
                    else:
                        metrics = no_pose_metrics()
                    metrics = add_session_fields(
                        metrics, frame_index, clock.elapsed_seconds()
                    )
                    evidence["legacy_metrics"] = metrics

                accumulator.add(evidence)
                if max_frames <= 0 or len(frames) < max_frames:
                    frames.append(evidence)
                frame_index += 1
                if max_frames > 0 and frame_index >= max_frames:
                    break
    finally:
        cap.release()

    processing_wall_s = time.perf_counter() - start_wall
    arrays = accumulator.finite_arrays()
    fs = accumulator.effective_sample_rate() or fps

    left_ref = kimore_reference_ex5_temporal_analysis(
        arrays["left_knee_sagittal_deg"], arrays["timestamps_s"], fs
    )
    right_ref = kimore_reference_ex5_temporal_analysis(
        arrays["right_knee_sagittal_deg"], arrays["timestamps_s"], fs
    )
    ref_summary = merge_side_events(left_ref, right_ref)
    descriptors = descriptive_temporal_features(arrays, ref_summary, fs)

    available = accumulator.available_count
    total = accumulator.total_added
    availability = (available / total) if total else 0.0
    quality_summary = {
        "frames_added": total,
        "available_frames": available,
        "unavailable_frames": accumulator.unavailable_count,
        "availability_rate": round(availability, 4),
        "evicted_frames": accumulator.evicted_count,
    }

    source = {
        "input_source": str(input_path),
        "video_fps_hz": round(video_fps, 4) if fps_from_video else None,
        "fps_used_hz": round(fps, 4),
        "frames_read": accumulator.total_added,
        "fps_trusted_from_video": fps_from_video,
        "processing_wall_seconds": round(processing_wall_s, 4),
    }

    export = build_session_export(
        source=source,
        method_provenance=METHOD_PROVENANCE,
        quality_summary=quality_summary,
        frames=frames,
        session_descriptors=descriptors,
        kimore_reference_analysis={"left": left_ref, "right": right_ref},
        limitations=LIMITATIONS,
        include_frames=True,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(export, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    if csv_path:
        _write_csv(csv_path, frames)

    print(f"[analyze_video] frames_added={total} available={available}")
    print(
        f"[analyze_video] reference event candidates="
        f"{ref_summary['n_reference_event_candidates']}"
    )
    print(f"[analyze_video] wrote {output_path}")
    return export


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="analyze_video",
        description="Offline BioGait KIMORE-informed session analyzer.",
    )
    parser.add_argument("--input", required=True, help="input video path")
    parser.add_argument("--output", required=True, help="output session JSON path")
    parser.add_argument("--model", default=None, help="PoseLandmarker .task path")
    parser.add_argument("--fps", type=float, default=None,
                        help="override video frame rate (Hz)")
    parser.add_argument("--max-frames", type=int, default=0,
                        help="process at most N frames (0 = all)")
    parser.add_argument("--csv", default=None,
                        help="optional per-frame CSV output path")
    parser.add_argument("--include-legacy", action="store_true",
                        help="also compute legacy screening metrics per frame")
    args = parser.parse_args(argv)

    try:
        analyze_video(
            Path(args.input),
            Path(args.output),
            model_path=Path(args.model) if args.model else None,
            fps_override=args.fps,
            max_frames=args.max_frames,
            csv_path=Path(args.csv) if args.csv else None,
            include_legacy=args.include_legacy,
        )
    except Exception as exc:  # lightweight CLI diagnostics
        print(f"[analyze_video] ERROR: {type(exc).__name__}: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
"""BioGait offline video analyzer (M4, Sprint A).

Reproducible experiment path: processes a video frame-by-frame with the same
MediaPipe PoseLandmarker model, extracts world-landmark research evidence,
accumulates a session, runs the offline source-aligned KIMORE reference
temporal analysis, and writes a structured, versioned session JSON.

No Qt GUI is required. A live webcam is NOT required.

Example:
    python biogait/analyze_video.py ^
        --input path/to/video.mp4 ^
        --output path/to/session.json

Timing is deterministic on the SOURCE VIDEO TIMELINE (frame_index / fps);
processing wall-clock time is never used as the scientific video timeline.
Offline analysis assumes a constant frame rate derived from video FPS metadata
(or an explicit --fps override); true per-frame source PTS recovery for
variable-frame-rate inputs is not claimed.

IMPORTANT: this is an OFFLINE research/experiment path. Results are
descriptive and reference-derived; they are not a clinical assessment.
The source-aligned KIMORE reference path requires a complete 30 Hz stream
with uniform 30 Hz timestamps; when the video frame rate differs or samples
are missing it returns a structured warning. An ENGINEERING_ADAPTED path at
the actual frame rate is also reported.

The project is PYTHON-ONLY. The reviewed original KIMORE source was written
in MATLAB; BioGait does not depend on or execute MATLAB. Source equations and
preprocessing conventions are re-implemented in Python for methodological
traceability. Numerical identity with the original MATLAB runtime has not
been established.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Optional

import cv2

import config

# Heavy runtime dependencies (cv2, mediapipe) are imported lazily below so the
# module stays importable in lightweight CI for argument/parse checks.
from metrics import add_session_fields, calculate_pose_metrics, no_pose_metrics
from runtime_utils import SourceVideoTimeline
from evidence_features import (
    build_frame_evidence,
    extract_normalized_landmarks,
    extract_world_landmarks,
)
from reference_temporal import (
    kimore_adapted_ex5_temporal_analysis,
    kimore_reference_ex5_temporal_analysis,
    side_event_summary,
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
TIMING_MODEL = "constant_frame_rate_from_fps"

METHOD_PROVENANCE = {
    "primary_outcomes": {
        "classification": "ENGINEERING_ADAPTED",
        "reference": "Capecci et al. 2019 (KIMORE), IEEE TNSRE",
        "doi": "10.1109/TNSRE.2019.2923060",
        "note": "Source-aligned KIMORE sagittal knee geometry (atan2 "
                "convention) adapted to MediaPipe world landmarks inferred "
                "from monocular RGB. Numerical identity with the original "
                "MATLAB runtime has not been established.",
    },
    "control_factors": {
        "classification": "ENGINEERING_ADAPTED",
        "wrist_proxy": (
            "MediaPipe wrist used as an ENGINEERING_ADAPTED proxy for the "
            "KIMORE Hand joint; not an exact kinematic equivalent."
        ),
        "knee_discrepancy": (
            "The KIMORE paper labels d_k as knee distance, while the reviewed "
            "feature-extraction source computes a signed Y-coordinate "
            "difference (deltayknee = Knee_R(:,2) - Knee_L(:,2)). BioGait "
            "preserves this discrepancy in provenance; the Euclidean "
            "knee_euclidean_3d_m is a separate DESCRIPTIVE value and is not "
            "presented as the source d_k."
        ),
        "cf_preprocessing": (
            "Sprint A implements CF geometry/evidence only. The reviewed "
            "source's later CF temporal trim/filter preprocessing is DEFERRED."
        ),
    },
    "filtering": {
        "reference": "kimore_reference_zero_phase_filter (REFERENCE_DERIVED, "
                     "offline, non-causal; FIXED order 3, 1 Hz, 30 Hz, "
                     "ba-form Butterworth + filtfilt)",
        "adapted": "kimore_adapted_zero_phase_filter (ENGINEERING_ADAPTED, "
                   "offline, non-causal; order 3, 1 Hz at the actual frame "
                   "rate — NOT the reference filter)",
        "causal": "CausalKimoreButterworth is an engineering adaptation with "
                  "phase delay and no clinical validation; not used here.",
    },
    "temporal_analysis": {
        "reference": "kimore_reference_ex5_temporal_analysis "
                     "(SOURCE-ALIGNED KIMORE REFERENCE PATH; REFERENCE_DERIVED; "
                     "requires a complete stream at 30 Hz with uniform 30 Hz "
                     "timestamps; otherwise returns a structured warning)",
        "adapted": "kimore_adapted_ex5_temporal_analysis (ENGINEERING_ADAPTED, "
                   "actual frame rate; not the 30 Hz KIMORE reference)",
    },
}

LIMITATIONS = [
    "BioGait is KIMORE-informed rather than a direct KIMORE reproduction. "
    "KIMORE uses Kinect-derived 3D skeletal coordinates, whereas BioGait "
    "uses MediaPipe world landmarks inferred from monocular RGB. Numerical "
    "equivalence and clinical validity are not assumed.",
    "The source-aligned KIMORE reference temporal analysis is non-causal "
    "(filtfilt) and must not be used as realtime causal filtering. It "
    "requires a complete, uniformly sampled stream at the 30 Hz reference "
    "convention (including uniform 30 Hz timestamps); otherwise it returns a "
    "structured warning and no filtering is applied.",
    "Offline analysis assumes a constant frame rate from video FPS metadata "
    "or an explicit --fps override (timing_model=constant_frame_rate_from_fps). "
    "Variable-frame-rate inputs should be transcoded/resampled to a known "
    "constant frame rate before scientific temporal comparison; no claim of "
    "true per-frame source PTS recovery is made.",
    "Reference full-sequence peak settings are not automatically valid for an "
    "arbitrary session length; detected events are candidates, not clinically "
    "valid repetitions, and no pass/fail is produced.",
    "Descriptive ROM / angular velocity values are kinematic summaries only; "
    "they are not clinical scores, pass/fail, or rehabilitation-quality "
    "judgements.",
    "MediaPipe wrist is a proxy for the KIMORE Hand joint; distances involving "
    "the wrist are engineering-adapted proxies.",
    "The KIMORE paper labels d_k as knee distance while the reviewed source "
    "computes a signed Y-coordinate difference; BioGait preserves this "
    "discrepancy and reports knee_delta_y_m (reference equation) separately "
    "from knee_euclidean_3d_m (descriptive).",
    "The reviewed source's CF temporal trim/filter preprocessing is DEFERRED; "
    "Sprint A exports CF geometry/evidence only.",
    "Bilateral repetition pairing is deferred (no temporal pairing tolerance "
    "is introduced here); per-side candidate counts are reported separately "
    "under each provenance branch.",
    "This output contains no personal identifiers and no local input paths; "
    "it should not be correlated to participant identity outside of a "
    "consented research protocol.",
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
        min_pose_detection_confidence=config.POSE_MIN_DETECTION_CONFIDENCE,
        min_pose_presence_confidence=config.POSE_MIN_DETECTION_CONFIDENCE,
        min_tracking_confidence=config.POSE_MIN_TRACKING_CONFIDENCE,
    )
    return mp_vision.PoseLandmarker.create_from_options(opts)


def _read_video_fps(cap) -> tuple[float, bool]:
    """Return (fps, trusted). fps=0.0 and trusted=False when metadata invalid.

    Uses ``math.isfinite`` so NaN/+-inf metadata is never accepted.
    """
    raw = float(cap.get(cv2.CAP_PROP_FPS))
    if not math.isfinite(raw) or raw <= 0:
        return 0.0, False
    return raw, True


def _resolve_fps(video_fps: float, fps_from_video: bool, override: Optional[float]) -> float:
    """Resolve the analysis frame rate without silently assuming a value.

    - Valid video FPS -> use it.
    - Else --fps override -> use it.
    - Else -> raise with a clear message requiring --fps.
    """
    if fps_from_video:
        return float(video_fps)
    if override is not None:
        if not math.isfinite(override) or override <= 0:
            raise ValueError(
                "invalid --fps override (must be a finite positive rate); "
                "provide a valid value for scientific temporal analysis"
            )
        return float(override)
    raise ValueError(
        "invalid or missing video FPS metadata; provide an explicit --fps "
        "override for scientific temporal analysis"
    )


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
        "knee_euclidean_3d_m",
        "knee_delta_y_m",
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
                    "knee_euclidean_3d_m": cf.get("knee_euclidean_3d_m"),
                    "knee_delta_y_m": cf.get("knee_delta_y_m"),
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
    """Run the offline analysis and write the structured session JSON.

    Console messages may print the local input path, but the persisted
    research JSON never does (see ``source`` metadata).

    Capture lifecycle: the VideoCapture is owned by this function and is
    released exactly once in the single outer ``finally``. That covers every
    failure point (capture open, FPS resolution, timeline construction, model
    / landmarker setup, frame processing, and export/write processing) without
    double-release ownership problems.
    """
    mp = __import__("mediapipe")
    cap = cv2.VideoCapture(str(input_path))
    try:
        if not cap.isOpened():
            raise RuntimeError(f"could not open video: {input_path}")

        video_fps, fps_from_video = _read_video_fps(cap)
        fps = _resolve_fps(video_fps, fps_from_video, fps_override)
        timeline = SourceVideoTimeline(fps)

        model = _ensure_model() if model_path is None else str(model_path)
        landmarker = _build_landmarker(model)

        accumulator = SessionAccumulator(max_frames=max_frames if max_frames > 0 else None)
        frames: list[dict] = []
        start_wall = time.perf_counter()

        with landmarker:
            frame_index = 0
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                timestamp_s = timeline.timestamp_seconds(frame_index)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                result = landmarker.detect_for_video(
                    img, timeline.video_timestamp_ms(frame_index)
                )

                world = extract_world_landmarks(result)
                evidence = build_frame_evidence(
                    world, frame_index, timestamp_s
                ).to_dict()

                if include_legacy:
                    lms = extract_normalized_landmarks(result)
                    if lms:
                        metrics = calculate_pose_metrics(lms)
                    else:
                        metrics = no_pose_metrics()
                    metrics = add_session_fields(
                        metrics, frame_index, timestamp_s
                    )
                    evidence["legacy_metrics"] = metrics

                accumulator.add(evidence)
                if max_frames <= 0 or len(frames) < max_frames:
                    frames.append(evidence)
                frame_index += 1
                if max_frames > 0 and frame_index >= max_frames:
                    break

        processing_wall_s = time.perf_counter() - start_wall
        aligned = accumulator.aligned_arrays()

        # The REFERENCE path receives the ACTUAL resolved fps and gates itself
        # to the 30 Hz convention; it never silently rounds e.g. 29.97 to 30.
        left_reference = kimore_reference_ex5_temporal_analysis(
            aligned["left_knee_sagittal_deg"], aligned["timestamps_s"], fps
        )
        right_reference = kimore_reference_ex5_temporal_analysis(
            aligned["right_knee_sagittal_deg"], aligned["timestamps_s"], fps
        )
        # The ADAPTED path uses the deterministic source-video timeline rate.
        left_adapted = kimore_adapted_ex5_temporal_analysis(
            aligned["left_knee_sagittal_deg"], aligned["timestamps_s"], fps
        )
        right_adapted = kimore_adapted_ex5_temporal_analysis(
            aligned["right_knee_sagittal_deg"], aligned["timestamps_s"], fps
        )
        reference_summary = side_event_summary(left_reference, right_reference)
        adapted_summary = side_event_summary(left_adapted, right_adapted)

        temporal_analysis = {
            "reference": {
                "classification": "REFERENCE_DERIVED",
                "offline": True,
                "left": left_reference,
                "right": right_reference,
                "summary": reference_summary,
            },
            "adapted": {
                "classification": "ENGINEERING_ADAPTED",
                "offline": True,
                "left": left_adapted,
                "right": right_adapted,
                "summary": adapted_summary,
            },
        }

        descriptors = descriptive_temporal_features(aligned, fps)

        total = accumulator.total_added
        available = accumulator.available_count
        availability = (available / total) if total else 0.0
        quality_summary = {
            "frames_added": total,
            "available_frames": available,
            "unavailable_frames": accumulator.unavailable_count,
            "availability_rate": round(availability, 4),
            "evicted_frames": accumulator.evicted_count,
        }

        # No local/absolute input path is persisted. Source metadata is neutral.
        source = {
            "source_type": "local_video",
            "timing_model": TIMING_MODEL,
            "video_fps_hz": round(video_fps, 4) if fps_from_video else None,
            "fps_used_hz": round(fps, 4),
            "frames_read": total,
            "fps_trusted_from_video": fps_from_video,
            "processing_wall_seconds": round(processing_wall_s, 4),
        }

        export = build_session_export(
            source=source,
            method_provenance=METHOD_PROVENANCE,
            quality_summary=quality_summary,
            frames=frames,
            session_descriptors=descriptors,
            temporal_analysis=temporal_analysis,
            limitations=LIMITATIONS,
            include_frames=True,
        )
        # Explicit data origin for this offline MediaPipe video session.
        export["data_origin"] = "REAL_VIDEO_MEDIAPIPE"
        export["processing_mode"] = "offline_mediapipe_video"

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            # allow_nan=False: invalid numerical values can never silently
            # become non-standard NaN/Infinity in the JSON.
            json.dumps(export, indent=2, ensure_ascii=False, allow_nan=False),
            encoding="utf-8",
        )
        if csv_path:
            _write_csv(csv_path, frames)

        print(f"[analyze_video] input={input_path}")
        print(f"[analyze_video] frames_added={total} available={available}")
        print(
            f"[analyze_video] reference candidates "
            f"(left={reference_summary['left_maxima_count']}, "
            f"right={reference_summary['right_maxima_count']}), "
            f"bilateral_pairing={reference_summary['bilateral_pairing_status']}"
        )
        print(f"[analyze_video] wrote {output_path}")
        return export
    finally:
        cap.release()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="analyze_video",
        description="Offline BioGait KIMORE-informed session analyzer.",
    )
    parser.add_argument("--input", required=True, help="input video path")
    parser.add_argument("--output", required=True, help="output session JSON path")
    parser.add_argument("--model", default=None, help="PoseLandmarker .task path")
    parser.add_argument("--fps", type=float, default=None,
                        help="override video frame rate (Hz; required if video "
                             "FPS metadata is invalid)")
    parser.add_argument("--max-frames", type=int, default=0,
                        help="process at most N frames (0 = all)")
    parser.add_argument("--csv", default=None,
                        help="optional per-frame CSV output path")
    parser.add_argument("--include-legacy", action="store_true",
                        help="also compute legacy screening metrics per frame")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
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
    except Exception as exc:  # lightweight CLI error reporting
        print(f"[analyze_video] ERROR: {type(exc).__name__}: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
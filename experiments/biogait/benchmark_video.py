"""BioGait offline video benchmark harness (Sprint A, early M4).

Measures per-frame processing time for the MediaPipe PoseLandmarker pipeline
on a local video. Only writes results when a real input video is supplied.

Timing for MediaPipe VIDEO inference uses the deterministic source-video
timeline (frame_index / fps), not the frame counter as fake milliseconds.
Processing wall-clock time is used only for the throughput/latency report.

Example:
    python experiments/biogait/benchmark_video.py --input path/to/video.mp4
    python experiments/biogait/benchmark_video.py --input path/to/video.mp4 ^
        --output path/to/benchmark.json

No GUI, no webcam, no network (unless the model file is missing).
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Optional

import cv2

# Repo-level biogait/ must be importable regardless of invocation directory.
_REPO_BIOGAIT = Path(__file__).resolve().parents[2] / "biogait"
sys.path.insert(0, str(_REPO_BIOGAIT))

from analyze_video import MODEL_PATH, _build_landmarker  # noqa: E402
from runtime_utils import SourceVideoTimeline  # noqa: E402


def _ensure_model() -> str:
    from analyze_video import _ensure_model as ensure

    return ensure()


def percentile_nearest_rank(sorted_values: list[float], percentile: float = 0.95) -> float:
    """Nearest-rank percentile on an already-sorted ascending sequence.

    index = ceil(percentile * n) - 1, clamped to [0, n-1]. This is a
    documented, deterministic convention (statistics.quantiles uses linear
    interpolation; here we intentionally use nearest-rank for parity with the
    benchmark reporting). Requires n >= 1.
    """
    n = len(sorted_values)
    if n == 0:
        raise ValueError("percentile_nearest_rank requires at least one value")
    idx = max(0, min(n - 1, math.ceil(percentile * n) - 1))
    return float(sorted_values[idx])


def benchmark(input_path: Path, output_path: Optional[Path], fps_override: Optional[float]) -> dict[str, Any]:
    mp = __import__("mediapipe")
    model = _ensure_model()
    landmarker = _build_landmarker(model)

    cap = cv2.VideoCapture(str(input_path))
    if not cap.isOpened():
        raise RuntimeError(f"could not open video: {input_path}")

    fps = float(cap.get(cv2.CAP_PROP_FPS))
    fps_from_video = fps > 0 and fps == fps
    if not fps_from_video:
        if fps_override is None:
            cap.release()
            raise ValueError(
                "invalid or missing video FPS metadata; provide an explicit "
                "--fps override"
            )
        fps = float(fps_override)
        fps_from_video = False
    timeline = SourceVideoTimeline(fps)

    total_frames = 0
    valid_pose_frames = 0
    world_available_frames = 0
    per_frame_ms: list[float] = []
    start = time.perf_counter()

    try:
        with landmarker:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                t0 = time.perf_counter()
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                result = landmarker.detect_for_video(
                    img, timeline.video_timestamp_ms(total_frames)
                )
                t1 = time.perf_counter()

                total_frames += 1
                per_frame_ms.append((t1 - t0) * 1000.0)

                cond = getattr(result, "pose_landmarks", None)
                if cond:
                    valid_pose_frames += 1
                    if getattr(result, "pose_world_landmarks", None):
                        world_available_frames += 1
    finally:
        cap.release()

    wall = time.perf_counter() - start
    sorted_ms = sorted(per_frame_ms)
    results: dict[str, Any] = {
        "source_type": "local_video",
        "timing_model": "constant_frame_rate_from_fps",
        "video_fps_hz": (round(fps, 4) if fps_from_video else None),
        "fps_used_hz": round(fps, 4),
        "fps_trusted_from_video": fps_from_video,
        "total_frames": total_frames,
        "valid_pose_frames": valid_pose_frames,
        "world_landmark_available_frames": world_available_frames,
        "world_landmark_availability_rate": (
            round(world_available_frames / valid_pose_frames, 4)
            if valid_pose_frames
            else None
        ),
        "processing_wall_seconds": round(wall, 4),
        "mean_ms_per_frame": round(statistics.fmean(per_frame_ms), 4) if per_frame_ms else None,
        "median_ms_per_frame": round(statistics.median(per_frame_ms), 4) if per_frame_ms else None,
        "p95_ms_per_frame": (
            round(percentile_nearest_rank(sorted_ms), 4) if sorted_ms else None
        ),
        "effective_throughput_fps": round(total_frames / wall, 4) if wall > 0 else None,
    }

    print(json.dumps(results, indent=2, allow_nan=False))
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(results, indent=2, allow_nan=False), encoding="utf-8"
        )
        print(f"[benchmark_video] wrote {output_path}")
    return results


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="benchmark_video",
        description="BioGait PoseLandmarker per-frame benchmark on a local video.",
    )
    parser.add_argument("--input", required=True, help="input video path")
    parser.add_argument("--output", default=None, help="optional JSON output path")
    parser.add_argument("--fps", type=float, default=None,
                        help="override video frame rate (Hz; required if video "
                             "FPS metadata is invalid)")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not Path(args.input).exists():
        print(f"[benchmark_video] ERROR: input does not exist: {args.input}")
        return 1
    try:
        benchmark(Path(args.input), Path(args.output) if args.output else None, args.fps)
    except Exception as exc:
        print(f"[benchmark_video] ERROR: {type(exc).__name__}: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
"""BioGait offline video benchmark harness (Sprint A, early M4).

Measures per-frame processing time for the MediaPipe PoseLandmarker pipeline
on a local video. Only writes results when a real input video is supplied.

Example:
    python experiments/biogait/benchmark_video.py --input path/to/video.mp4
    python experiments/biogait/benchmark_video.py --input path/to/video.mp4 ^
        --output path/to/benchmark.json

No GUI, no webcam, no network (unless the model file is missing).
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "biogait"))

from analyze_video import MODEL_PATH, _build_landmarker  # noqa: E402


def _ensure_model() -> str:
    from analyze_video import _ensure_model as ensure

    return ensure()


def benchmark(input_path: Path, output_path: Path) -> dict[str, Any]:
    mp = __import__("mediapipe")
    model = _ensure_model()
    landmarker = _build_landmarker(model)

    cap = cv2.VideoCapture(str(input_path))
    if not cap.isOpened():
        raise RuntimeError(f"could not open video: {input_path}")

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
                result = landmarker.detect_for_video(img, total_frames + 1)
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
    results: dict[str, Any] = {
        "input": str(input_path),
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
            round(sorted(per_frame_ms)[int(0.95 * len(per_frame_ms))], 4) if per_frame_ms else None
        ),
        "effective_throughput_fps": round(total_frames / wall, 4) if wall > 0 else None,
    }

    print(json.dumps(results, indent=2))
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(results, indent=2), encoding="utf-8"
        )
        print(f"[benchmark_video] wrote {output_path}")
    return results


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="benchmark_video",
        description="BioGait PoseLandmarker per-frame benchmark on a local video.",
    )
    parser.add_argument("--input", required=True, help="input video path")
    parser.add_argument("--output", default=None, help="optional JSON output path")
    args = parser.parse_args(argv)

    if not Path(args.input).exists():
        print(f"[benchmark_video] ERROR: input does not exist: {args.input}")
        return 1
    try:
        benchmark(Path(args.input), Path(args.output) if args.output else None)
    except Exception as exc:
        print(f"[benchmark_video] ERROR: {type(exc).__name__}: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
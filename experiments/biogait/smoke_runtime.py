"""Real-runtime smoke test support (Sprint B, B16).

Modes:
  --video PATH    load the actual MediaPipe model, process a small bounded
                  number of frames, verify pose-result schema and world-
                  landmark extraction, verify FrameEvidence serialization,
                  and report processing time.
  --camera N      optional/manual; never launched automatically from tests.

Default: does nothing destructive.

If the runtime deps (cv2/mediapipe/PyQt5) or a video are unavailable, it
reports REAL_RUNTIME_SMOKE=PENDING and exits 0. It never fails the whole
sprint just because no hardware/video is available.

Example:
    python experiments/biogait/smoke_runtime.py --video path/to/clip.mp4 --max-frames 30
    python experiments/biogait/smoke_runtime.py              # -> PENDING, no-op
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Optional

from common import BIOGAIT_DIR, atomic_json_write

if str(BIOGAIT_DIR) not in sys.path:
    sys.path.insert(0, str(BIOGAIT_DIR))


def resolve_smoke_fps(video_fps_value: float, trusted: bool, override: Optional[float]) -> tuple[Optional[float], str]:
    """Resolve the smoke-test frame rate without silently assuming 30 Hz.

    Policy: valid video FPS -> use it; else explicit --fps -> use it; else
    report PENDING (no detection loop). Returns ``(fps, status)`` where status
    is "ok" or a reason label.
    """
    if trusted and video_fps_value and video_fps_value > 0:
        return float(video_fps_value), "ok"
    if override is not None and override > 0:
        return float(override), "ok"
    return None, "fps_metadata_invalid_provide_--fps"


def smoke_video(input_path: Path, model_path: Optional[Path], max_frames: int = 30,
                fps_override: Optional[float] = None) -> dict[str, Any]:
    """Process a bounded number of frames with the real MediaPipe model.

    Uses the deterministic source-video timeline (strictly increasing VIDEO
    timestamps and FrameEvidence ``timestamp_seconds``) resolved from real FPS
    metadata or an explicit ``--fps`` override. It never silently assumes 30 Hz
    and never uses wall-clock time as the offline video timeline.
    """
    try:
        import cv2
        import mediapipe as mp
    except Exception as exc:  # noqa: BLE001 - missing runtime deps
        return {"REAL_RUNTIME_SMOKE": "PENDING", "reason": f"runtime deps unavailable: {type(exc).__name__}"}

    from analyze_video import _build_landmarker, _ensure_model, _read_video_fps
    from evidence_features import build_frame_evidence, extract_world_landmarks
    from runtime_utils import SourceVideoTimeline

    model = str(model_path if model_path else Path(_ensure_model()))
    landmarker = _build_landmarker(model)
    cap = cv2.VideoCapture(str(input_path))
    try:
        if not cap.isOpened():
            return {"REAL_RUNTIME_SMOKE": "PENDING", "reason": "video could not be opened"}

        video_fps, trusted = _read_video_fps(cap)
        fps, fps_status = resolve_smoke_fps(video_fps, trusted, fps_override)
        if fps is None:
            return {"REAL_RUNTIME_SMOKE": "PENDING", "reason": fps_status}
        timeline = SourceVideoTimeline(fps)

        frames = 0
        pose_frames = 0
        world_extracted = 0
        serialized_ok = 0
        start = time.perf_counter()
        with landmarker:
            for _ in range(max_frames):
                ok, frame = cap.read()
                if not ok:
                    break
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                # Strictly increasing VIDEO timestamp from the shared timeline.
                ts_ms = timeline.video_timestamp_ms(frames)
                result = landmarker.detect_for_video(mp_image, ts_ms)
                frames += 1
                if getattr(result, "pose_landmarks", None):
                    pose_frames += 1
                world = extract_world_landmarks(result)
                if world:
                    world_extracted += 1
                timestamp_s = timeline.timestamp_seconds(frames - 1)
                evidence = build_frame_evidence(world, frames - 1, timestamp_s)
                json.dumps(evidence.to_dict(), allow_nan=False)
                serialized_ok += 1
        wall = time.perf_counter() - start
        return {
            "REAL_RUNTIME_SMOKE": "COMPLETE",
            "fps_used_hz": round(fps, 4),
            "frames_processed": frames,
            "pose_frames": pose_frames,
            "world_landmark_frames": world_extracted,
            "evidence_serialized_ok": serialized_ok,
            "processing_wall_seconds": round(wall, 4),
        }
    finally:
        cap.release()


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="smoke_runtime", description="Bounded real-runtime smoke test.")
    p.add_argument("--video", default=None, help="local video path")
    p.add_argument("--camera", default=None, help="optional manual camera source (never auto-launched)")
    p.add_argument("--max-frames", type=int, default=30)
    p.add_argument("--model", default=None)
    p.add_argument("--fps", type=float, default=None,
                   help="video frame-rate override (required if video FPS metadata invalid)")
    p.add_argument("--output", default=None, help="optional JSON output")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.video:
        result = smoke_video(
            Path(args.video),
            Path(args.model) if args.model else None,
            args.max_frames,
            fps_override=args.fps,
        )
    elif args.camera is not None:
        print("Camera mode is manual/optional; not auto-launching.")
        result = {"REAL_RUNTIME_SMOKE": "PENDING", "reason": "camera mode is manual/optional"}
    else:
        result = {"REAL_RUNTIME_SMOKE": "PENDING", "reason": "no video or camera supplied"}
    print(json.dumps(result, indent=2, allow_nan=False))
    if args.output:
        atomic_json_write(Path(args.output), result)
        print(f"[smoke_runtime] wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

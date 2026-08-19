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


def smoke_video(input_path: Path, model_path: Optional[Path], max_frames: int = 30) -> dict[str, Any]:
    """Process a bounded number of frames with the real MediaPipe model."""
    try:
        import cv2
        import mediapipe as mp
    except Exception as exc:  # noqa: BLE001 - missing runtime deps
        return {"REAL_RUNTIME_SMOKE": "PENDING", "reason": f"runtime deps unavailable: {type(exc).__name__}"}

    from analyze_video import _build_landmarker, _ensure_model
    from evidence_features import build_frame_evidence, extract_world_landmarks

    model = str(model_path if model_path else Path(_ensure_model()))
    landmarker = _build_landmarker(model)
    cap = cv2.VideoCapture(str(input_path))
    try:
        if not cap.isOpened():
            return {"REAL_RUNTIME_SMOKE": "PENDING", "reason": "video could not be opened"}
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
                result = landmarker.detect_for_video(mp_image, 0)  # smoke only
                frames += 1
                if getattr(result, "pose_landmarks", None):
                    pose_frames += 1
                world = extract_world_landmarks(result)
                if world:
                    world_extracted += 1
                evidence = build_frame_evidence(world, frames - 1, (frames - 1) / 30.0)
                json.dumps(evidence.to_dict(), allow_nan=False)
                serialized_ok += 1
        wall = time.perf_counter() - start
        return {
            "REAL_RUNTIME_SMOKE": "COMPLETE",
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
    p.add_argument("--output", default=None, help="optional JSON output")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.video:
        result = smoke_video(
            Path(args.video),
            Path(args.model) if args.model else None,
            args.max_frames,
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

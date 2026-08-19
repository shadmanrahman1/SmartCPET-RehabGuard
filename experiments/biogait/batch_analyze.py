"""Offline batch analyzer (Sprint B, B10).

Processes supported local videos sequentially through ``biogait/analyze_video.py``
(no pose-inference logic is duplicated here). Writes one session JSON per
video plus an aggregate manifest.

Supports:
    --input-dir  scan a directory for supported video files
    --manifest   a JSON list of {video, sequence_key} (or entries)
    --output-dir  where session JSONs + aggregate manifest are written
    --model, --fps

Policies:
- No local/absolute input paths are written into persistent result JSON.
- Neutral opaque sequence keys are used (no participant names).
- Failure of one video records a sanitized status and continues unless --fail-fast.

Example:
    python experiments/biogait/batch_analyze.py --input-dir clips --output-dir out
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Optional

from common import atomic_json_write, opaque_key

VIDEO_EXTENSIONS = (".mp4", ".avi", ".mov", ".mkv", ".webm")


def _resolve_sources(input_dir: Optional[Path], manifest: Optional[Path]) -> list[dict]:
    """Resolve [{video, sequence_key}] from an input dir or manifest."""
    if manifest is not None:
        data = json.loads(Path(manifest).read_text(encoding="utf-8"))
        raw = data.get("entries", data) if isinstance(data, dict) else data
        sources = []
        for entry in raw:
            if isinstance(entry, dict) and "video" in entry:
                sources.append(
                    {
                        "video": Path(entry["video"]),
                        "sequence_key": entry.get("sequence_key")
                        or opaque_key(str(Path(entry["video"]))),
                    }
                )
        return sources
    if input_dir is not None:
        sources = []
        for ext in VIDEO_EXTENSIONS:
            for f in sorted(glob.glob(str(Path(input_dir) / f"**/*{ext}"), recursive=True)):
                p = Path(f)
                sources.append(
                    {"video": p, "sequence_key": opaque_key(p.name)}
                )
        return sources
    raise ValueError("provide --input-dir or --manifest")


def _analyze_video_module():
    # Lazily import analyze_video (its cv2/mediapipe import only matters at run
    # time on a real environment, not at import time).
    import analyze_video as _av
    return _av


def _process_one(av, video: Path, out_json: Path, model, fps_override) -> dict:
    export = av.analyze_video(
        video,
        out_json,
        model_path=Path(model) if model else None,
        fps_override=float(fps_override) if fps_override is not None else None,
    )
    atomic_json_write(out_json, export)
    return {
        "sequence_key": opaque_key(video.name),
        "data_origin": "REAL_VIDEO_MEDIAPIPE",
        "status": "ok",
        "output_file": out_json.name,
    }


def run_batch(
    *,
    input_dir: Optional[Path] = None,
    manifest: Optional[Path] = None,
    output_dir: Path,
    model: Optional[str] = None,
    fps_override: Optional[float] = None,
    fail_fast: bool = False,
) -> dict:
    av = _analyze_video_module()
    sources = _resolve_sources(input_dir, manifest)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    running = []
    for source in sources:
        video = source["video"]
        seq_key = source["sequence_key"]
        out_json = output_dir / f"{seq_key}.json"
        try:
            running.append(_process_one(av, video, out_json, model, fps_override))
        except Exception as exc:  # noqa: BLE001 - batch robustness boundary
            running.append(
                {
                    "sequence_key": seq_key,
                    "data_origin": "REAL_VIDEO_MEDIAPIPE",
                    "status": "failed",
                    "error_type": type(exc).__name__,
                }
            )
            if fail_fast:
                break

    aggregate = {
        "experiment": "batch_analyze",
        "schema_version": "1.0",
        "n_requested": len(sources),
        "n_ok": sum(1 for r in running if r["status"] == "ok"),
        "n_failed": sum(1 for r in running if r["status"] == "failed"),
        "results": running,
    }
    atomic_json_write(output_dir / "manifest.json", aggregate)
    return aggregate


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="batch_analyze",
        description="Offline batch analyzer wrapping analyze_video.py.",
    )
    p.add_argument("--input-dir", default=None)
    p.add_argument("--manifest", default=None)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--model", default=None)
    p.add_argument("--fps", type=float, default=None)
    p.add_argument("--fail-fast", action="store_true")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    aggregate = run_batch(
        input_dir=Path(args.input_dir) if args.input_dir else None,
        manifest=Path(args.manifest) if args.manifest else None,
        output_dir=Path(args.output_dir),
        model=args.model,
        fps_override=args.fps,
        fail_fast=args.fail_fast,
    )
    print(json.dumps(aggregate, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

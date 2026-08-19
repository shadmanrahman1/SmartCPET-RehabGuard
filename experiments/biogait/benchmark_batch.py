"""Runtime benchmark batch + summary (Sprint B, B11).

Runs the per-video benchmark (benchmark_video.py) across multiple local videos
and summarizes the results. Numeric values are only produced from real
execution — they are never invented. If no real video is supplied, the tool
writes no numeric benchmark result and reports REAL_VIDEO_BENCHMARK=PENDING.

Per-video collected: total frames, valid-pose frames, world-landmark
availability, processing wall time, mean/median/p95 ms per frame, throughput
FPS, source FPS, resolution, timing model.

Example:
    python experiments/biogait/benchmark_batch.py --input-dir clips --output-dir out
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Optional

from common import atomic_json_write, opaque_key

VIDEO_EXTENSIONS = (".mp4", ".avi", ".mov", ".mkv", ".webm")


def _resolve_videos(input_dir: Optional[Path]) -> list[Path]:
    if input_dir is None:
        return []
    videos = []
    for ext in VIDEO_EXTENSIONS:
        videos.extend(
            Path(f) for f in sorted(glob.glob(str(Path(input_dir) / f"**/*{ext}"), recursive=True))
        )
    return videos


def _aggregate(rows: list[dict]) -> dict:
    """Summarize successful benchmark rows (numeric aggregates only)."""
    ok = [r for r in rows if r.get("status") == "ok" and r.get("mean_ms_per_frame") is not None]
    if not ok:
        return {"REAL_VIDEO_BENCHMARK": "PENDING", "note": "no real measured benchmark data"}
    means = [r["mean_ms_per_frame"] for r in ok]
    medians = [r["median_ms_per_frame"] for r in ok]
    p95s = [r["p95_ms_per_frame"] for r in ok if r["p95_ms_per_frame"] is not None]
    throughputs = [r["effective_throughput_fps"] for r in ok if r["effective_throughput_fps"] is not None]
    return {
        "REAL_VIDEO_BENCHMARK": "COMPLETE",
        "n_videos": len(rows),
        "n_success": len(ok),
        "aggregate": {
            "total_frames": sum(r["total_frames"] for r in ok),
            "world_landmark_availability_rate": (
                round(sum(r["world_landmark_availability_rate"] or 0.0 for r in ok) / len(ok), 4)
            ),
            "mean_ms_per_frame_over_videos": round(statistics.fmean(means), 4),
            "median_ms_per_frame_over_videos": round(statistics.median(medians), 4),
            "p95_ms_per_frame_over_videos": (
                round(statistics.fmean(p95s), 4) if p95s else None
            ),
            "effective_throughput_fps_over_videos": (
                round(statistics.fmean(throughputs), 4) if throughputs else None
            ),
        },
    }


def run_benchmark_batch(input_dir: Optional[Path], output_dir: Path, fps_override=None) -> dict:
    import benchmark_video as bv

    videos = _resolve_videos(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    per_video = []
    for video in videos:
        key = opaque_key(video.name)
        try:
            row = bv.benchmark(video, output_dir / f"{key}.json", fps_override)
            row["sequence_key"] = key
            row["status"] = "ok"
            row["filename"] = video.name
            per_video.append(row)
        except Exception as exc:  # noqa: BLE001 - batch robustness boundary
            per_video.append(
                {
                    "sequence_key": key,
                    "filename": video.name,
                    "status": "failed",
                    "error_type": type(exc).__name__,
                }
            )

    summary = _aggregate(per_video)
    result = {
        "experiment": "benchmark_batch",
        "schema_version": "1.0",
        "timing_model": "constant_frame_rate_from_fps",
        "n_videos_requested": len(videos),
        "summary": summary,
        "per_video": per_video,
    }
    atomic_json_write(output_dir / "benchmark_batch.json", result)

    with open(output_dir / "benchmark_batch.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "sequence_key", "filename", "status", "fps_used_hz",
                "frame_width_px", "frame_height_px", "total_frames",
                "world_landmark_availability_rate", "processing_wall_seconds",
                "mean_ms_per_frame", "median_ms_per_frame", "p95_ms_per_frame",
                "effective_throughput_fps", "error_type",
            ],
            extrasaction="ignore",
        )
        writer.writeheader()
        for row in per_video:
            writer.writerow(row)

    return result


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="benchmark_batch",
        description="Runtime benchmark across local videos (measured values only).",
    )
    p.add_argument("--input-dir", default=None)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--fps", type=float, default=None)
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    result = run_benchmark_batch(
        Path(args.input_dir) if args.input_dir else None,
        Path(args.output_dir),
        args.fps,
    )
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

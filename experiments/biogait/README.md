# BioGait Experiments (Sprint A, early M4)

Reproducible offline research harnesses for the BioGait module.

> These harnesses are OFFLINE and require a local video file and the
> MediaPipe PoseLandmarker model. They do NOT use the camera or Qt GUI.
> Results are descriptive/reference-derived; they are not clinical assessments.

## Requirements

- Python 3.10 / 3.11 with `biogait/requirements.txt` installed
- `pose_landmarker_lite.task` present in `biogait/` (auto-downloaded on first run)
- A local recorded video to process

## Offline session analysis

Runs the KIMORE-informed evidence pipeline and writes a structured,
versioned session JSON (plus an optional per-frame CSV).

```powershell
# from the repo root
python biogait/analyze_video.py --input path/to/video.mp4 --output out/session.json
python biogait/analyze_video.py --input path/to/video.mp4 --output out/session.json --csv out/frames.csv
python biogait/analyze_video.py --input path/to/video.mp4 --output out/session.json --max-frames 1800
python biogait/analyze_video.py --input path/to/video.mp4 --output out/session.json --fps 30
```

- If a video has valid FPS metadata it is used; otherwise an explicit `--fps`
  override is required for scientific temporal analysis (no silent 30 Hz
  assumption, no wall-clock fallback).
- Timing is deterministic on the source-video timeline (`frame_index / fps`);
  MediaPipe VIDEO timestamps are strictly increasing milliseconds from the
  same helper. Processing wall time is used only for benchmarks.

Output includes:

- per-frame research evidence (world-landmark quality, primary outcomes,
  control factors)
- session descriptors (duration, effective sample rate, descriptive ROM and
  angular velocity)
- offline KIMORE reference temporal analysis — EXACT path (complete 30 Hz
  stream) and ACTUAL-fps ADAPTED path — with per-side candidate counts and
  durations; bilateral pairing is deferred (no combined repetition count)
- neutral source metadata (`source_type`, FPS values, `frames_read`); the
  local input path is never persisted

## Per-frame benchmark

```powershell
python experiments/biogait/benchmark_video.py --input path/to/video.mp4
python experiments/biogait/benchmark_video.py --input path/to/video.mp4 --output out/benchmark.json
```

Reports total frames, valid-pose frames, world-landmark availability,
processing wall time, mean/median/p95 ms per frame, and effective throughput
FPS. MediaPipe VIDEO timestamps come from the same deterministic source-video
timeline helper (never `frame_count + 1`). If video FPS metadata is invalid,
an explicit `--fps` override is required. Values are measured — never
fabricated.

## Notes

- No secrets, no participant identifiers, and no private biomedical
  recordings should ever be placed under `experiments/`.
- Benchmark/analysis outputs should not be committed unless they are part of
  a documented, consented experiment.
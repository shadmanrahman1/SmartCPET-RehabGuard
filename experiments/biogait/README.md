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
```

Output includes:

- per-frame research evidence (world-landmark quality, primary outcomes,
  control factors)
- session descriptors (duration, effective sample rate, descriptive ROM and
  angular velocity)
- offline KIMORE reference temporal analysis (event candidates, candidate
  repetition durations)

## Per-frame benchmark

```powershell
python experiments/biogait/benchmark_video.py --input path/to/video.mp4
python experiments/biogait/benchmark_video.py --input path/to/video.mp4 --output out/benchmark.json
```

Reports total frames, valid-pose frames, world-landmark availability,
processing wall time, mean/median/p95 ms per frame, and effective throughput
FPS. Values are measured — never fabricated.

## Notes

- No secrets, no participant identifiers, and no private biomedical
  recordings should ever be placed under `experiments/`.
- Benchmark/analysis outputs should not be committed unless they are part of
  a documented, consented experiment.
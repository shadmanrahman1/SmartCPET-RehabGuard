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
  assumption, no wall-clock fallback, and 29.97 is never rounded to 30).
- Timing is deterministic on the source-video timeline (`frame_index / fps`);
  MediaPipe VIDEO timestamps are strictly increasing milliseconds from the
  same helper. Processing wall time is used only for benchmarks. Offline
  analysis assumes a constant frame rate (`timing_model:
  constant_frame_rate_from_fps`); variable-frame-rate inputs should be
  transcoded/resampled to a known constant frame rate before scientific
  temporal comparison.

Output includes:

- per-frame research evidence (feature-gated world-landmark quality, primary
  outcomes, control factors)
- session descriptors (duration, effective sample rate, descriptive ROM and
  angular velocity)
- `temporal_analysis` with SEPARATE provenance branches:
  - `reference` (source-aligned KIMORE reference path; REFERENCE_DERIVED; only
    runs on a complete stream at 30 Hz with uniform 30 Hz timestamps)
  - `adapted` (ENGINEERING_ADAPTED at the actual frame rate)
  - each branch has per-side analysis and a per-side summary (left/right
    maxima counts and candidate durations); bilateral pairing is deferred (no
    combined repetition count)
- neutral source metadata (`source_type`, `timing_model`, FPS values,
  `frames_read`); the local input path is never persisted

## Per-frame benchmark

```powershell
python experiments/biogait/benchmark_video.py --input path/to/video.mp4
python experiments/biogait/benchmark_video.py --input path/to/video.mp4 --output out/benchmark.json
```

Reports total frames, valid-pose frames, world-landmark availability,
processing wall time, mean/median/p95 ms per frame, and effective throughput
FPS. p95 uses a documented nearest-rank calculation (`ceil(0.95*n)-1`,
clamped). MediaPipe VIDEO timestamps come from the same deterministic
source-video timeline helper (never `frame_count + 1`), and results carry the
same `timing_model` metadata. If video FPS metadata is invalid, an explicit
`--fps` override is required. Values are measured — never fabricated.

## Sprint B — evaluation & reproducibility tooling

The tools below are offline, synthetic-fixture-safe, and never download a
dataset or launch a camera automatically. Provenance is never mixed; no
clinical score is produced. Full narrative in `docs/biogait-sprint-b-evaluation.md`
and claim boundaries in `docs/biogait-claim-matrix.md`.

- `common.py` — opaque keys, atomic `allow_nan=False` JSON, frame conversion.
- `environment_report.py` — neutral non-identifying environment report.
- `kimore_adapter.py` — local-only KIMORE adapter (`--inspect`, `--load`,
  `--synthetic`); real `KIMORE_DATASET_ROOT` validation is PENDING.
- `experiment_manifest.py` — reproducible enumeration + subject-disjoint split.
- `evaluate_kimore_ex5.py` — source-skeleton evaluator of the source-aligned
  kinematics (`--synthetic` or `--manifest`).
- `kimore_mapping_report.py` — paper/source discrepancy report (JSON + Markdown).
- `fps_sensitivity.py` — sampling-rate sensitivity (30 Hz = REFERENCE anchor).
- `missingness_sensitivity.py` — controlled missing-data robustness.
- `landmark_robustness.py` — feature-loss availability matrix.
- `batch_analyze.py` — batch wrapper around `analyze_video.py`.
- `benchmark_batch.py` — multi-video runtime benchmark summary.
- `aggregate_results.py` — provenance-separated aggregation (JSON + CSV).
- `make_paper_tables.py` / `make_paper_figures.py` — data-gated paper artifacts
  (figures need matplotlib; PENDING_DATA otherwise).
- `smoke_runtime.py` — bounded real-runtime smoke test (`--video` / `--camera`).
- `results/` — policy: raw data/video/paths/names are never committed; only
  `README.md` + `evaluation_status.json` are tracked.

## Notes

- No secrets, no participant identifiers, and no private biomedical
  recordings should ever be placed under `experiments/`.
- Benchmark/analysis outputs should not be committed unless they are part of
  a documented, consented experiment.
- Requires `requirements-evaluation.txt` for the optional matplotlib figure
  generator; the unit tests need only `biogait/requirements-tests.txt`.
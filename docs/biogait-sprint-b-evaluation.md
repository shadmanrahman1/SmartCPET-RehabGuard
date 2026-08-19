# BioGait Sprint B — Evaluation, Robustness, Reproducibility (conference-paper friendly)

This document explains the Sprint B evaluation work for the BioGait module:
what was built, why it does not validate MediaPipe against Kinect, and what is
still pending. It is a research/reproducibility narrative — not a clinical
validation claim.

## 1. Sprint A architecture (context)

Sprint A (merged) added a KIMORE-informed research core to Module 2 / BioGait:

- `evidence_features.py` — source-aligned sagittal knee angle (reviewed `atan2`
  equation), feature-specific quality gating, and control-factor geometry.
- `temporal_filters.py` — a FIXED-parameter reference zero-phase filter
  (order 3, 1 Hz, 30 Hz; ba-form Butterworth + `filtfilt`), a separate
  ENGINEERING_ADAPTED zero-phase filter at the actual frame rate, and a causal
  Butterworth (no zero-phase equivalence).
- `reference_temporal.py` — the SOURCE-ALIGNED KIMORE reference path
  (discard-first-9 zero-based samples = source `10:end`, sign-flip on
  consecutive diff outside [-100, 100], extrema at max/√2, min peak distance
  ⌊n/10⌋) plus an ACTUAL-fps ADAPTED path, with timestamp/rate validation.
- `session_analysis.py` + `analyze_video.py` — a bounded accumulator, pure
  descriptive session metrics, and a versioned session export whose
  `temporal_analysis` keeps REFERENCE_DERIVED and ENGINEERING_ADAPTED branches
  strictly separate.

## 2. Sprint B evaluation question

Sprint B asks: **can the Python source-aligned kinematic implementation run
correctly and robustly on the native KIMORE Ex5 skeletal representation, and
how do its descriptive/adapted outputs change under sampling-rate changes and
missing data?** It also builds the reproducibility, runtime, aggregation, and
paper-artifact infrastructure.

## 3. KIMORE native-skeleton evaluation

`experiments/biogait/kimore_adapter.py` is a local-only adapter that maps native
KIMORE joints (shoulder / hand / hip / knee / ankle) to a normalized Python
representation. `evaluate_kimore_ex5.py` feeds those joints into the
source-aligned knee PO + control-factor geometry and the reference temporal
path. This evaluates the **source-aligned re-implementation**, not MediaPipe.

## 4. Why this does NOT validate MediaPipe against Kinect

- Values are measured on MediaPipe world landmarks in Sprint A; on synthetic or
  unavailable licensed KIMORE skeletons here.
- No synchronized RGB + Kinect capture exists, and no defensible alignment
  method has been specified.
- Therefore **MediaPipe-vs-Kinect numerical validation stays DEFERRED**
  (`evaluation_status.json`), and no claim of Kinect/MediaPipe equivalence is
  made. The claim matrix (`docs/biogait-claim-matrix.md`) forbids
  "equivalent to Kinect" phrasing.

## 5. Sampling-rate sensitivity

`experiments/biogait/fps_sensitivity.py` resamples a complete angle sequence
(15–60 Hz) in the experiment layer only. The 30 Hz result stays the
REFERENCE_DERIVED anchor; other rates are ENGINEERING_ADAPTED. Recorded
descriptors: ROM, peak/mean angular velocity, and candidate-event counts, as
drift metrics. This is not clinical accuracy.

## 6. Missing-data robustness

`experiments/biogait/missingness_sensitivity.py` injects deterministic
missingness (0–30%, plus optional burst dropout) at a fixed seed and records PO
coverage, reference/adapted warning behavior, descriptive-feature availability,
and rolling-window availability. Production analysis is not modified to
interpolate gaps; the experiment measures the current conservative behavior.

## 7. Feature-specific quality degradation

`experiments/biogait/landmark_robustness.py` builds a landmark-loss availability
matrix (e.g., a missing wrist removes only wrist-based CFs; a missing ankle
removes only that side's primary outcome). This is the feature-specific gating
introduced in Sprint A, confirmed by construction.

## 8. Runtime evaluation

`benchmark_video.py` (single video) and `benchmark_batch.py` (multiple videos)
measure per-frame latency, availability, and throughput. Numbers are only ever
produced from real execution; with no real video the tools report
`REAL_VIDEO_BENCHMARK=PENDING` and write no numeric result. `smoke_runtime.py`
provides a bounded real-runtime smoke check (`REAL_RUNTIME_SMOKE`).

## 9. Reproducibility

- `environment_report.py` writes a neutral, non-identifying environment report.
- `experiment_manifest.py` enumerates datasets with neutral opaque keys and
  provides subject-disjoint split tooling (fixed seed; a subject never spans
  folds). No ML is trained.
- `aggregate_results.py` never mixes provenance categories; per-provenance CSV
  plus a tagged aggregate JSON are emitted.
- `make_paper_tables.py` / `make_paper_figures.py` emit tables/figures only when
  data exists; absent data is reported as PENDING_DATA, never fabricated.
- A GitHub Actions workflow (`biogait-tests.yml`) runs compileall + the full
  test suite headlessly.

## 10. Remaining clinical limitations

- No clinical correctness, diagnosis, rehabilitation-quality judgement, or
  good/bad squat label is produced anywhere.
- No cPO / cCF / cTS prediction; the EAAQ and KIMORE clinical scores are not
  reproduced.
- Reference events are candidates, not clinically validated repetitions.
- Reference analysis is offline/non-causal.
- Real-dataset (KIMORE), real-video benchmark, and MediaPipe-vs-Kinect
  validation remain PENDING / DEFERRED until licensed/synchronized data is
  available under a consented protocol.

## 11. Data origin vs method provenance

Every experiment result carries an explicit `data_origin` distinct from its
`method_provenance`:

- `data_origin`: `SYNTHETIC_FIXTURE` / `REAL_KIMORE_NATIVE_SKELETON` /
  `REAL_VIDEO_MEDIAPIPE` / `UNKNOWN_UNVALIDATED`.
- `method_provenance`: `REFERENCE_DERIVED` / `ENGINEERING_ADAPTED` /
  `DESCRIPTIVE` (and `EXPERIMENTAL` for robustness experiments).
- `execution_status`: `COMPLETE` / `PENDING`, etc.

`REFERENCE_DERIVED` describes the METHOD and never implies real KIMORE data.
Synthetic experiments validate software behavior, provenance routing, and
robustness logic — they do NOT validate clinical accuracy, MediaPipe accuracy,
KIMORE dataset performance, or participant performance. Native KIMORE
evaluation, when real licensed data is supplied, validates source-data
execution of the Python feature pipeline; it still does NOT validate
MediaPipe-vs-Kinect accuracy.

## Status manifest

See `experiments/biogait/results/evaluation_status.json` for the current
statuses of each evaluation artifact, including per-table status classes
(EMPIRICAL_COMPLETE / SYNTHETIC_ONLY / PENDING_DATA).

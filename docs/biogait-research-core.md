# BioGait Research Core (Sprint A: M2 + M3 + early M4)

Module 2 / BioGait research-core engineering. This document describes the
runtime/data-flow and what was introduced in Sprint A.

> This sprint introduces **no new rehabilitation assessment method** in the
> sense of a clinically scored test. All new components are
> REFERENCE_DERIVED / ENGINEERING_ADAPTED / DESCRIPTIVE and carry **no**
> clinical validation claims. The legacy BioGait scientific scoring logic is
> unchanged.

## Scope

- Module 2 / BioGait only. Module 1 / CPET was not touched.
- `biogait/metrics.py` was not modified.

## Runtime data flow

The live Qt runtime (`app_qt.py` → `ui_worker.py` → MediaPipe → `metrics.py`)
is preserved. One PoseLandmarker result now feeds two consumers:

```
             PoseLandmarkerResult
                   │
           ┌───────┴────────┐
           ↓                ↓
   normalized          world landmarks
   landmarks           (pose_world_landmarks)
           ↓                ↓
   legacy metrics    research evidence
   (metrics.py)      (evidence_features.py)
```

- Legacy metrics keep receiving exactly what they expect.
- If world landmarks are missing, the legacy pipeline still works; research
  evidence is marked unavailable with an explicit reason.

## Feature modules

| Module | Purpose | Classification |
|--------|---------|----------------|
| `biogait/evidence_features.py` | World-landmark extraction, exact KIMORE sagittal knee geometry (`atan2` convention), Euclidean control factors, torso area, shoulder coordinates, frame evidence schema | ENGINEERING_ADAPTED / DESCRIPTIVE / REFERENCE_DERIVED (equation) |
| `biogait/temporal_filters.py` | KIMORE reference zero-phase filter (ba-form Butterworth + `filtfilt`); causal Butterworth adaptation (SOS) | REFERENCE_DERIVED (offline) / ENGINEERING_ADAPTED (causal) |
| `biogait/reference_temporal.py` | Offline KIMORE Ex5 reference analysis — EXACT path (requires complete 30 Hz stream; trim 10, sign-flip when consecutive diff >100°, ba-form `filtfilt`, extrema at max/√2, min peak distance ⌊n/10⌋) + ACTUAL-fps ADAPTED path | REFERENCE_DERIVED (exact) / ENGINEERING_ADAPTED (adapted) / OFFLINE |
| `biogait/session_analysis.py` | Bounded session accumulator, aligned arrays (gaps preserved as None), effective sample rate, descriptive features (ROM, angular velocity), versioned session schema | DESCRIPTIVE |
| `biogait/analyze_video.py` | Offline video analyzer CLI producing structured session JSON/CSV | ENGINEERING |

## Frame evidence schema

`FrameEvidence` (dataclass) per frame:

- `schema_version`, `exercise`, `frame_index`, `timestamp_seconds`
- `quality` — `available`, `missing_landmarks`, `mean_visibility`, `reason`
  (`reason` is `ok`, `missing_world_landmarks`, `low_landmark_visibility`, or
  `degenerate_knee_geometry`)
- `primary_outcomes` — left/right sagittal knee angles (degrees) using the
  exact reviewed Ex5 convention:
  `degrees(atan2(hip_y-knee_y, hip_z-knee_z) + atan2(knee_y-ankle_y, ankle_z-knee_z))`

Missing evidence is always `None` (never `0`); no fake measurements.
Degenerate (zero-length) hip-knee or knee-ankle segments also produce `None`
primary outcomes with the explicit `degenerate_knee_geometry` reason. The
reference representation is not clamped to 0..180 degrees.

## Temporal / session analysis

- Bounded/testable session accumulator. `aligned_arrays()` preserves EVERY
  retained frame: no-pose/unavailable frames stay explicit `None` entries, so
  temporal gaps are never silently compressed. `finite_arrays()` (valid-only)
  is used only where valid-only data is explicitly acceptable (sample-rate
  estimation).
- The EXACT KIMORE reference path
  (`kimore_reference_ex5_temporal_analysis`) requires a complete (no `None`)
  sample stream at the 30 Hz reference convention. Otherwise it returns a
  structured warning (`missing_samples_require_resampling` or
  `reference_requires_30hz_or_resampling`) and no filtering/peak detection
  runs. No interpolation/resampling is introduced in this sprint.
- An ACTUAL-frame-rate ADAPTED path
  (`kimore_adapted_ex5_temporal_analysis`) is provided for the video's real
  frame rate; it is classified ENGINEERING_ADAPTED, never REFERENCE_DERIVED.
- Reference event counts and candidate repetition durations are reported PER
  SIDE (`left_reference_maxima_count`, `right_reference_maxima_count`, per-side
  durations). Bilateral pairing is deferred (`bilateral_pairing_status:
  "deferred"`); no combined/repetition union count is produced.
- Descriptive features: session duration, sample rate, left/right ROM,
  left/right peak & mean absolute angular velocity, ROM difference. Angular
  velocity is computed on index-aligned adjacent samples only when both angles
  and both timestamps are valid and increasing; gaps are skipped, never
  bridged.

## Offline analyzer

```
python biogait/analyze_video.py --input video.mp4 --output session.json
```

- No Qt GUI; same MediaPipe PoseLandmarker model; frame-by-frame processing.
- Timing is deterministic on the SOURCE VIDEO TIMELINE: `timestamp_seconds =
  frame_index / fps`, and MediaPipe receives strictly increasing millisecond
  VIDEO timestamps from the same helper. Processing wall clock is used only
  for the benchmark, never as the scientific video timeline.
- Frame rate resolution: valid video FPS is used; otherwise an explicit
  `--fps` override is used; otherwise analysis stops with a clear message
  requiring `--fps`. No silent 30 Hz assumption.
- Writes a versioned JSON with neutral source metadata (`source_type`,
  `video_fps_hz`, `fps_used_hz`, `frames_read` — the local input path is never
  persisted), method provenance, quality summary, frames, session descriptors,
  exact + adapted KIMORE reference analysis, and limitations. Optional
  per-frame CSV.
- Becomes the reproducible BioGait experiment path.

## UI integration

- New `evidence_ready` signal emitted (throttled) from `ui_worker.py`.
- Every processed frame contributes to evidence availability accounting,
  including NO_POSE frames (which add unavailable evidence using the current
  frame index/timestamp). Availability rate on the panel reflects the retained
  rolling window (`retained_availability_rate`), matching the window the
  displayed session ROM is computed from.
- `ResearchEvidencePanel` in the dashboard:
  - L/R sagittal knee angle
  - world-landmark quality + evidence availability
  - session ROM (after data accumulates)
- The panel is information-neutral: no correct/incorrect, no clinical score,
  no pass/fail, and no medical colour semantics.
- The legacy risk gauge is now captioned **"Legacy experimental baseline —
  not clinically validated."**

## Benchmarks

`experiments/biogait/benchmark_video.py` measures per-frame wall time,
valid-pose/world-landmark availability, mean/median/p95 ms/frame, and
effective throughput FPS on a supplied local video. Values are measured, never
fabricated.

## Claim boundaries

- No new clinical thresholds, risk weights, or clinical scoring were added.
- No ML models or LLM integration.
- Reference events are candidates only; they are not clinically valid
  repetitions and not pass/fail.
- Reference analysis is offline/non-causal and unsuitable for realtime
  causal decisions.
- BioGait is KIMORE-informed, not a direct KIMORE reproduction (see
  `evidence/kimore-ex5-squat.md`).
- KIMORE exercise-performance scores are clinician-derived through the
  Exercise Accuracy Assessment Questionnaire (EAAQ); BioGait does NOT
  reproduce or predict those clinical scores in Sprint A. EAAQ is a
  task-independent assessment framework used because of the lack of validated
  clinical tools for rating individual therapeutic-exercise performance; it is
  not an externally validated universal clinical scale.

## Tests

`tests/test_biogait_evidence_features.py`,
`tests/test_biogait_temporal_filters.py`,
`tests/test_biogait_session_analysis.py`,
`tests/test_biogait_reference_temporal.py`,
`tests/test_biogait_offline_schema.py`,
`tests/test_biogait_cli_load.py`.

No camera, GUI, network, or model download is required by the test suite.
Synthetic deterministic data is used throughout.
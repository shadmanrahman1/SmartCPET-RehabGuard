# BioGait Research Core (Sprint A: M2 + M3 + early M4)

Module 2 / BioGait research-core engineering. This document describes the
runtime/data-flow and what was introduced in Sprint A.

> This sprint introduces **no new rehabilitation assessment method** in the
> sense of a clinically scored test. All new components are
> REFERENCE_DERIVED / ENGINEERING_ADAPTED / DESCRIPTIVE and carry **no**
> clinical validation claims. The legacy BioGait scientific scoring logic is
> unchanged.
>
> The project is **Python-only**. The reviewed original KIMORE source was
> written in MATLAB; BioGait does not depend on or execute MATLAB. Source
> equations and preprocessing conventions are re-implemented in Python for
> methodological traceability.

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
- Both the live worker and the offline analyzer use the same PoseLandmarker
  Lite model with the same confidence settings from `config.py`.

## Feature modules

| Module | Purpose | Classification |
|--------|---------|----------------|
| `biogait/evidence_features.py` | World-landmark extraction, source-aligned KIMORE sagittal knee geometry (`atan2` convention), feature-specific quality gating, control factors (incl. `knee_delta_y_m` + descriptive `knee_euclidean_3d_m`), torso area, shoulder coordinates, frame evidence schema | ENGINEERING_ADAPTED / DESCRIPTIVE / REFERENCE_DERIVED (equations) |
| `biogait/temporal_filters.py` | REFERENCE zero-phase filter (FIXED order 3, 1 Hz, 30 Hz, ba-form Butterworth + `filtfilt`, rejects non-finite); ADAPTED zero-phase filter at the actual fs; causal Butterworth adaptation (SOS) | REFERENCE_DERIVED (offline reference) / ENGINEERING_ADAPTED (adapted + causal) |
| `biogait/reference_temporal.py` | Offline SOURCE-ALIGNED KIMORE reference path (complete stream at 30 Hz + uniform 30 Hz timestamps; MATLAB `10:end` trim = discard first 9 in zero-based Python, sign-flip when consecutive diff outside [-100,+100], ba-form `filtfilt`, extrema at max/√2, min peak distance ⌊n/10⌋) + ACTUAL-fps ADAPTED path | REFERENCE_DERIVED (reference) / ENGINEERING_ADAPTED (adapted) / OFFLINE |
| `biogait/session_analysis.py` | Bounded session accumulator, aligned arrays (gaps preserved as None), effective sample rate, descriptive features (ROM, angular velocity), versioned session schema with `temporal_analysis` provenance branches | DESCRIPTIVE |
| `biogait/analyze_video.py` | Offline video analyzer CLI producing structured session JSON/CSV | ENGINEERING |

## Frame evidence schema

`FrameEvidence` (dataclass) per frame:

- `schema_version`, `exercise`, `frame_index`, `timestamp_seconds`
- `quality` — `available` (BOTH primary knee outcomes available; NOT "every
  CF available"), `left_po_available`, `right_po_available`,
  `primary_outcomes_complete`, `control_factors_complete`,
  `missing_or_low_quality_landmarks`, `mean_visibility`, and `reason`
  (`ok` / `partial` / `missing_world_landmarks` / `low_landmark_visibility` /
  `non_finite_landmark` / `degenerate_knee_geometry`)
- `primary_outcomes` — left/right sagittal knee angles (degrees) using the
  source-aligned reviewed Ex5 convention:
  `degrees(atan2(hip_y-knee_y, hip_z-knee_z) + atan2(knee_y-ankle_y, ankle_z-knee_z))`
- `control_factors` — feature-gated values including `knee_delta_y_m`
  (reference equation: signed Y-coordinate difference) and
  `knee_euclidean_3d_m` (descriptive Euclidean; NOT presented as source d_k)

Quality gating is PER FEATURE using `config.MIN_LANDMARK_VISIBILITY`. A
landmark is available when present, finite (x/y/z/visibility not NaN/±inf), and
above the threshold. A missing wrist never erases a valid knee primary
outcome. Missing evidence is always `None` (never `0`); non-finite values are
never emitted as measurements.

## Temporal / session analysis

- Bounded/testable session accumulator. `aligned_arrays()` preserves EVERY
  retained frame: no-pose/unavailable frames stay explicit `None` entries, so
  temporal gaps are never silently compressed. `finite_arrays()` (valid-only)
  is used only where valid-only data is explicitly acceptable (sample-rate
  estimation).
- The SOURCE-ALIGNED reference path
  (`kimore_reference_ex5_temporal_analysis`) receives the ACTUAL resolved fps
  and gates itself: it requires a complete (no `None`/NaN/±inf) sample stream
  at the 30 Hz reference convention and, when timestamps are supplied,
  finite/strictly-increasing/uniform-30 Hz timestamps. Violations return a
  structured warning (`missing_samples_require_resampling`,
  `reference_requires_30hz_or_resampling`, or
  `reference_requires_uniform_30hz_timestamps_or_resampling`) and no
  filtering/peak detection runs. It only ever calls the fixed-parameter
  reference filter; it never passes an arbitrary FPS to it.
- The ACTUAL-frame-rate ADAPTED path
  (`kimore_adapted_ex5_temporal_analysis`) is provided for the video's real
  frame rate using the separate adapted zero-phase filter; it is classified
  ENGINEERING_ADAPTED, never REFERENCE_DERIVED. Supplied timestamps must be
  finite, strictly increasing, and uniform at the supplied rate
  (`adapted_requires_uniform_sampling_or_resampling` otherwise).
- Event `time_s` refers to the original source-session timeline (derived as
  `original_index / fs` when timestamps are absent, or the supplied timestamp
  when present) — never restarted at zero after the initial trim.
- The session export (`temporal_analysis`) keeps SEPARATE provenance branches
  — `reference` (REFERENCE_DERIVED) and `adapted` (ENGINEERING_ADAPTED) — each
  with per-side analysis and a generic per-side summary (left/right maxima
  counts and candidate durations) plus `bilateral_pairing_status: "deferred"`.
  No combined/union repetition count is produced, and descriptive session
  metrics never carry adapted event counts under "reference" names.
- Descriptive features (session_descriptors) contain only: session duration,
  effective sample rate, left/right ROM, left/right peak & mean absolute
  angular velocity, and ROM difference. Angular velocity is computed on
  index-aligned adjacent samples only when both angles and both timestamps are
  valid and increasing; gaps are skipped, never bridged.

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
  requiring `--fps`. No silent 30 Hz assumption, and 29.97 is never rounded to
  30 — the reference path simply returns its 30 Hz gate warning.
- Constant-frame-rate assumption (`timing_model: constant_frame_rate_from_fps`
  in the exported source metadata): offline analysis assumes a constant frame
  rate derived from video FPS metadata or an explicit override. Variable-frame
  -rate inputs should be transcoded/resampled to a known constant frame rate
  before scientific temporal comparison; no claim of true per-frame source
  PTS recovery is made.
- Writes a versioned JSON with neutral source metadata (`source_type`,
  `timing_model`, `video_fps_hz`, `fps_used_hz`, `frames_read` — the local
  input path is never persisted), method provenance, quality summary, frames,
  session descriptors, `temporal_analysis` (reference + adapted branches), and
  limitations. JSON serialization uses `allow_nan=False`. Optional per-frame
  CSV.
- Becomes the reproducible BioGait experiment path.

## UI integration

- New `evidence_ready` signal emitted (throttled) from `ui_worker.py`.
- Every processed frame contributes to evidence availability accounting,
  including NO_POSE frames (which add unavailable evidence using the current
  frame index/timestamp).
- Current-state fields come from the LATEST PROCESSED frame — a NO_POSE frame
  never displays an older (stale) knee angle as current.
- The panel shows:
  - L/R sagittal knee (current frame)
  - Current PO evidence (latest frame)
  - Rolling PO availability (retained rolling window)
  - Rolling L ROM / Rolling R ROM (last-300-processed-frame window — never
    billed as whole-session ROM)
- The panel is information-neutral: no correct/incorrect, no clinical score,
  no pass/fail, and no medical colour semantics.
- The legacy risk gauge is now captioned **"Legacy experimental baseline —
  not clinically validated."**

## Benchmarks

`experiments/biogait/benchmark_video.py` measures per-frame wall time,
valid-pose/world-landmark availability, mean/median/p95 ms/frame, and
effective throughput FPS on a supplied local video. p95 uses a documented
nearest-rank calculation (`ceil(0.95*n)-1`, clamped). MediaPipe VIDEO
timestamps come from the same deterministic source-video timeline helper, and
results carry the same `timing_model` metadata. Values are measured, never
fabricated.

## Claim boundaries

- No new clinical thresholds, risk weights, or clinical scoring were added.
- No ML models (RF/XGBoost/TCN/ST-GCN) or LLM/MedGemma integration.
- Reference events are candidates only; they are not clinically valid
  repetitions and not pass/fail.
- Reference analysis is offline/non-causal and unsuitable for realtime causal
  decisions.
- BioGait is KIMORE-informed, not a direct KIMORE reproduction (see
  `evidence/kimore-ex5-squat.md`). The algorithmic conventions and parameters
  follow the reviewed KIMORE source; numerical identity with the original
  MATLAB runtime has not been established.
- The KIMORE paper labels d_k as knee distance while the reviewed source
  computes a signed Y-coordinate difference; BioGait preserves this
  discrepancy and reports `knee_delta_y_m` (reference equation) separately
  from `knee_euclidean_3d_m` (descriptive).
- CF temporal trim/filter preprocessing from the reviewed source is DEFERRED;
  Sprint A exports CF geometry/evidence only.
- KIMORE exercise-performance scores are clinician-derived through the
  Exercise Accuracy Assessment Questionnaire (EAAQ). The paper reports
  discriminative validity and inter-rater reliability of EAAQ from prior work
  while also noting the lack of established validated clinical tools
  specifically for rating individual therapeutic-exercise performance. BioGait
  does NOT reproduce or predict those clinical scores (cPO/cCF/cTS) in Sprint
  A and makes no Fugl-Meyer association.
- MediaPipe world landmarks are 3D coordinates in meters with the midpoint of
  the hips as the origin (a MediaPipe convention, not a camera-centered
  frame); Kinect and MediaPipe coordinate frames are not assumed to be
  numerically equivalent.

## Tests

`tests/test_biogait_evidence_features.py`,
`tests/test_biogait_temporal_filters.py`,
`tests/test_biogait_session_analysis.py`,
`tests/test_biogait_reference_temporal.py`,
`tests/test_biogait_offline_schema.py`,
`tests/test_biogait_cli_load.py`.

No camera, GUI, network, or model download is required by the test suite.
Synthetic deterministic data is used throughout.
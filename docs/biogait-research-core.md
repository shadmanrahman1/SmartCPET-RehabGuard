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
| `biogait/evidence_features.py` | World-landmark extraction, KIMORE sagittal knee geometry, Euclidean control factors, torso area, shoulder coordinates, frame evidence schema | ENGINEERING_ADAPTED / DESCRIPTIVE |
| `biogait/temporal_filters.py` | KIMORE reference zero-phase filter; causal Butterworth adaptation | REFERENCE_DERIVED (offline) / ENGINEERING_ADAPTED (causal) |
| `biogait/reference_temporal.py` | Offline KIMORE Ex5 reference temporal analysis (trim, sign correction, zero-phase `sosfiltfilt`/`filtfilt` filtering, extrema at max/√2, min peak distance ⌊n/10⌋) | REFERENCE_DERIVED / OFFLINE |
| `biogait/session_analysis.py` | Bounded session accumulator, effective sample rate, descriptive features (ROM, angular velocity), versioned session schema | DESCRIPTIVE |
| `biogait/analyze_video.py` | Offline video analyzer CLI producing structured session JSON/CSV | ENGINEERING |

## Frame evidence schema

`FrameEvidence` (dataclass) per frame:

- `schema_version`, `exercise`, `frame_index`, `timestamp_seconds`
- `quality` — `available`, `missing_landmarks`, `mean_visibility`, `reason`
- `coordinate_source` — `mediapipe_world`
- `provenance` — reference, DOI, ENGINEERING_ADAPTED note, wrist-proxy note
- `primary_outcomes` — left/right sagittal knee angles (degrees)
- `control_factors` — wrist/shoulder/hip/knee/ankle distances, wrist-shoulder
  distances, torso area, shoulder X/Z coordinates
- `metadata` — `wrist_proxy_for_kimore_hand = true`

Missing evidence is always `None` (never `0`); no fake measurements.

## Temporal / session analysis

- Bounded/testable session accumulator; finite arrays from available frames
  only; effective sample rate estimated from the median inter-sample interval.
- Reference temporal analysis runs per knee side offline; per-side maxima
  events are merged for a bilateral (squat) candidate summary.
- Descriptive features: session duration, sample rate, left/right ROM,
  left/right peak & mean absolute angular velocity, ROM difference, reference
  event candidates, candidate repetition durations.

## Offline analyzer

```
python biogait/analyze_video.py --input video.mp4 --output session.json
```

- No Qt GUI; same MediaPipe PoseLandmarker model; frame-by-frame processing.
- Writes a versioned JSON with source info, method provenance, quality
  summary, frames, session descriptors, KIMORE reference analysis, and
  limitations. Optional per-frame CSV.
- Becomes the reproducible BioGait experiment path.

## UI integration

- New `evidence_ready` signal emitted (throttled) from `ui_worker.py`.
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

## Tests

`tests/test_biogait_evidence_features.py`,
`tests/test_biogait_temporal_filters.py`,
`tests/test_biogait_session_analysis.py`,
`tests/test_biogait_reference_temporal.py`,
`tests/test_biogait_offline_schema.py`.

No camera, GUI, network, or model download is required by the test suite.
Synthetic deterministic data is used throughout.
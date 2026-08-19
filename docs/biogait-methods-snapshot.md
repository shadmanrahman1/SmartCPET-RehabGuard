# BioGait Methods Snapshot (Sprint C)

> Coding-side source of truth for the paper Methods. No fabricated result
> values appear here. This describes the method; evaluation status lives in
> `experiments/biogait/results/evaluation_status.json` and
> `docs/biogait-claim-matrix.md`.

## Input
- Offline mediapipe video session (`data_origin=REAL_VIDEO_MEDIAPIPE`) or live
  MediaPipe camera evidence; native KIMORE skeletons via the local adapter
  (`REAL_KIMORE_NATIVE_SKELETON`); synthetic fixtures are explicitly
  `SYNTHETIC_FIXTURE`.

## Pose model
- MediaPipe PoseLandmarker **Lite** with engineering confidence settings from
  `config.py` (`POSE_MIN_DETECTION_CONFIDENCE`, `POSE_MIN_TRACKING_CONFIDENCE`).
  It infers 3D **world landmarks in meters with the hip midpoint as origin**
  from monocular RGB. Kinect/MediaPipe numerical equivalence is not assumed.

## Normalized vs world landmarks
- Normalized (image-space) landmarks feed the legacy screening metrics.
- Research evidence uses **world landmarks** (`evidence_features.py`).

## Feature geometry
- Source-aligned sagittal knee angle (reviewed `atan2` convention):
  `degrees(atan2(hip_y-knee_y, hip_z-knee_z) + atan2(knee_y-ankle_y, ankle_z-knee_z))`.
- Feature-specific quality gating via `config.MIN_LANDMARK_VISIBILITY`;
  non-finite landmarks are treated as unavailable.
- Control factors (distances, torso area, shoulder x/z) with `knee_delta_y_m`
  (reference equation) vs `knee_euclidean_3d_m` (descriptive).

## KIMORE source alignment
- MATLAB source `angle = angle(10:end)` (1-based) -> discard the first 9
  zero-based Python samples (`values[9:]`).
- Sign-flip on consecutive difference outside [-100, +100] (not ±360 unwrap).

## Reference filtering
- `kimore_reference_zero_phase_filter` — FIXED order 3, 1 Hz, 30 Hz;
  ba-form `butter` + `filtfilt` (non-causal, offline). Rejects None/NaN/±inf.

## Adapted filtering
- `kimore_adapted_zero_phase_filter(values, fs)` — order 3, 1 Hz at the actual
  frame rate; ENGINEERING_ADAPTED (never the reference filter).

## Temporal candidates
- Maxima at `max(signal)/√2`; minima on `max(signal)-signal` at `max/√2`;
  min peak distance `floor(n/10)`. Candidates are NOT clinically valid
  repetitions.

## Quality gating
- Per-feature availability; `available` = both primary knee outcomes.
  Current-PO state: `complete` / `partial` / `unavailable`.

## Data origin
- Enforced `data_origin` on every result and kept distinct from
  `method_provenance` (`REFERENCE_DERIVED` / `ENGINEERING_ADAPTED` /
  `DESCRIPTIVE` / `EXPERIMENTAL`).

## Evaluation framework
- Local-only KIMORE adapter; source-skeleton evaluator; FPS/missingness/
  landmark robustness experiments; runtime benchmark; provenance-separated
  aggregator; paper tables/figures (data-gated).

## Explanation layer
- Deterministic template explainer (default) plus optional OpenRouter remote
  explainer (`openrouter` mode) that receives ONLY structured evidence and
  returns validated structured output; unsafe/malformed output is rejected and
  replaced by the template.

## Claim boundaries
- No clinical score, diagnosis, treatment recommendation, pass/fail squat, or
  rehabilitation-quality judgement is produced. Synthetic experiments validate
  software/provenance/robustness, not clinical, MediaPipe, or KIMORE accuracy.

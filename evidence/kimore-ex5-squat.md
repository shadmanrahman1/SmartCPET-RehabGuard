# KIMORE Exercise 5 (Squat) — BioGait Evidence Row

> Method provenance: **REFERENCE_DERIVED / ENGINEERING_ADAPTED / DESCRIPTIVE**
> as labelled per component below. Sections are locked scientific decisions
> for Sprint A and are implemented in `biogait/`.

## Reference

- **Paper:** Capecci et al., 2019. *The KIMORE Dataset: KInematic Assessment of
  MOvement and Clinical Scores for Remote Monitoring of Physical
  REhabilitation*. IEEE Transactions on Neural Systems and Rehabilitation
  Engineering.
- **DOI:** [10.1109/TNSRE.2019.2923060](https://doi.org/10.1109/TNSRE.2019.2923060)
- **Reviewed source implementation:** `petteriTeikari/KiMoRe_wrapper`
  - `matlab/matlab_original/feat_extract_Ex5.m`
  - `matlab/matlab_original/filtering.m`

## Original context (KIMORE)

- KIMORE measures motor performance in physical rehabilitation with a
  **Kinect RGB-D sensor** providing high-confidence 3D skeletal coordinates.
- Exercise 5 is a **squat** (repeated knee flexion/extension).
- In KIMORE, exercise-performance scores are **clinician-derived** through the
  Exercise Accuracy Assessment Questionnaire (EAAQ), a task-independent
  assessment framework. The KIMORE paper notes the lack of validated clinical
  tools specifically for rating individual therapeutic-exercise performance;
  EAAQ was used as that assessment framework. EAAQ is not an externally
  validated universal clinical scale and should not be overclaimed as one.

## BioGait adaptation context

- BioGait uses **monocular RGB** inference via MediaPipe PoseLandmarker
  (`pose_landmarker_lite.task`), producing both normalized image landmarks and
  **world landmarks** — real-world 3D coordinates in meters with the
  **midpoint of the hips as the origin** (a MediaPipe convention, not a
  camera-centered frame).
- The research pipeline consumes **world landmarks** when available.
- MediaPipe **WRIST is a proxy** for the KIMORE **Hand** joint; it is an
  ENGINEERING_ADAPTED proxy, not an exact kinematic Hand equivalent.
- Kinect and MediaPipe axes/coordinate frames are **not** assumed to be
  numerically equivalent.

> **BioGait is KIMORE-informed rather than a direct KIMORE reproduction.
> KIMORE uses Kinect-derived 3D skeletal measurements, whereas BioGait uses
> MediaPipe world landmarks inferred from monocular RGB. Numerical equivalence
> and clinical validity are not assumed.**

## PO mapping (Primary Outcomes)

| KIMORE concept | BioGait implementation | Classification |
|----------------|------------------------|----------------|
| Sagittal knee angle | `kimore_reference_sagittal_knee_angle_yz(hip, knee, ankle)` — the exact reviewed Ex5 convention: `degrees(atan2(hip_y-knee_y, hip_z-knee_z) + atan2(knee_y-ankle_y, ankle_z-knee_z))` per side | ENGINEERING_ADAPTED (coordinate transfer) / REFERENCE_DERIVED (equation) |

- The reference representation is **not** a clamped 0..180 vector angle and
  is **not** converted into a conventional unsigned joint angle.
- Degenerate (zero-length) hip-knee or knee-ankle segments yield `None`
  (never a fake 0-degree measurement).
- No correct/incorrect labels are produced.
- Values are `None` (never 0) when evidence is unavailable; no fake
  measurements are generated.

## CF mapping (Control Factors)

| KIMORE concept | BioGait implementation | Classification |
|----------------|------------------------|----------------|
| Hand distance | wrist-to-wrist Euclidean 3D distance (wrist = Hand proxy) | ENGINEERING_ADAPTED |
| Shoulder width | shoulder-to-shoulder distance | ENGINEERING_ADAPTED |
| Hip width | hip-to-hip distance | ENGINEERING_ADAPTED |
| Knee width | knee-to-knee distance | ENGINEERING_ADAPTED |
| Ankle width | ankle-to-ankle distance | ENGINEERING_ADAPTED |
| Hand-shoulder distance | left/right wrist-to-shoulder distances | ENGINEERING_ADAPTED |
| Torso area | quadrilateral LS-RS-RH-LH decomposed into two Heron triangles | ENGINEERING_ADAPTED |

## Filtering

- **Reference (offline):** Butterworth, order 3, cutoff 1 Hz, reference
  sample rate 30 Hz, reproduced as `[b, a] = butter(order=3, cutoff=1 Hz,
  fs=30 Hz)` + `filtfilt(b, a, x)` — zero-phase, non-causal.
  Classification: REFERENCE_DERIVED / OFFLINE ONLY / NON-CAUSAL.
  The EXACT reference path only runs on a complete stream at 30 Hz.
- **Causal adaptation:** `CausalKimoreButterworth` — stateful SOS filtering.
  Classification: ENGINEERING_ADAPTED. Not `filtfilt`-equivalent, introduces
  phase delay, not clinically validated; causal output does not equal
  reference output.

## Reference temporal analysis

Offline reference path describing the KIMORE Ex5 event-extraction convention:

1. KIMORE source retains samples `10:end` in MATLAB (1-based) indexing —
   equivalent to discarding the first 9 samples (`values[9:]`) in zero-based
   Python; trimmed index 0 maps to original Python index 9 / MATLAB sample
   10;
2. exact sign-flip correction (negate a sample when the consecutive angle
   difference is below −100° or above +100° — NOT a ±360 unwrap);
3. ba-form `filtfilt` reference filter (30 Hz, order 3, 1 Hz);
4. maxima at `max(signal)/√2`;
5. minima on `max(signal) − signal` at `max(transformed)/√2`;
6. minimum peak distance `⌊n/10⌋`.

- The EXACT path requires a complete (no missing samples) stream at the
  30 Hz reference convention; otherwise it returns a structured warning
  (`missing_samples_require_resampling` or
  `reference_requires_30hz_or_resampling`) and does NOT run filtering/peak
  detection. An ENGINEERING_ADAPTED path at the video's actual frame rate is
  also reported and is never labelled REFERENCE_DERIVED.
- Detected events are **candidate** repetition events — **not** clinically
  valid repetitions — and the path produces no pass/fail.
- The KIMORE acquisition protocol involved repeated exercise execution; its
  full-sequence peak settings are **not automatically valid** for an
  arbitrary live session length.

Classification: REFERENCE_DERIVED / OFFLINE / NOT REALTIME.

## Descriptive metrics

- Session duration, effective sample rate.
- Left/right knee ROM (max−min, degrees).
- Left/right angular velocity (finite difference Δangle/Δt), peak and mean
  absolute values. Intervals with a missing angle or non-increasing
  timestamp are skipped — gaps are never bridged.
- Left-right ROM difference.
- Per-side reference maxima counts and per-side candidate repetition
  durations; bilateral pairing is **deferred** (`bilateral_pairing_status:
  "deferred"`). No combined/repetition union count is produced.

These are **descriptive kinematics only** — not clinical risk, pass/fail,
rehabilitation scores, or movement-quality scores.

## Claim boundaries

- No component in this document claims clinical validity.
- No component produces a clinical diagnosis or rehabilitation quality score.
- The legacy BioGait risk gauge remains a separate, visually labelled
  experimental non-clinical baseline.
- Offline reference analysis is unsuitable as a realtime causal decision path.

## Implementation files

- `biogait/evidence_features.py` — extraction, geometry, frame evidence schema
- `biogait/temporal_filters.py` — reference + causal filters
- `biogait/reference_temporal.py` — offline KIMORE Ex5 reference analysis
- `biogait/session_analysis.py` — accumulator, descriptive features, export
- `biogait/analyze_video.py` — offline video analyzer CLI

## Validation status

None for all components (REFERENCE_DERIVED / ENGINEERING_ADAPTED /
DESCRIPTIVE). Internal unit tests cover geometry, filtering, and session
logic with deterministic synthetic data; no clinical claims are made.
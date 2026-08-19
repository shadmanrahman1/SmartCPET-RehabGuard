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
  **Kinect RGB-D sensor** providing Kinect-derived 3D skeletal coordinates.
- Exercise 5 is a **squat** (repeated knee flexion/extension).
- The KIMORE paper itself notes that the Exercise-5 knee-flexion primary
  outcome can show systematic bias and joint occlusion. BioGait therefore
  applies pose-quality gating and conservative claims about the adapted
  measurements; Kinect is not treated as a perfect gold-standard sensor.
- In KIMORE, exercise-performance scores are **clinician-derived** through the
  Exercise Accuracy Assessment Questionnaire (EAAQ). EAAQ is the
  clinician-assessment framework used by KIMORE. The paper reports
  discriminative validity and inter-rater reliability of EAAQ from prior
  work, while also noting the lack of established validated clinical tools
  specifically for rating individual therapeutic-exercise performance. EAAQ
  should not be overclaimed as an externally validated universal clinical
  scale, and BioGait does not reproduce or predict KIMORE clinical scores
  (cPO, cCF, cTS) in Sprint A. No association with scales such as Fugl-Meyer
  is claimed.
- The project is **Python-only**. The reviewed original KIMORE source was
  written in MATLAB; BioGait does not depend on or execute MATLAB. Source
  equations and preprocessing conventions are re-implemented in Python for
  methodological traceability.

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
| Sagittal knee angle | `kimore_reference_sagittal_knee_angle_yz(hip, knee, ankle)` — the source-aligned reviewed Ex5 convention: `degrees(atan2(hip_y-knee_y, hip_z-knee_z) + atan2(knee_y-ankle_y, ankle_z-knee_z))` per side. The equation is directly source-derived; numerical identity with the original MATLAB runtime has not been established | ENGINEERING_ADAPTED (coordinate transfer) / REFERENCE_DERIVED (equation) |

- The reference representation is **not** a clamped 0..180 vector angle and
  is **not** converted into a conventional unsigned joint angle.
- Degenerate (zero-length) hip-knee or knee-ankle segments yield `None`
  (never a fake 0-degree measurement).
- No correct/incorrect labels are produced.
- Values are `None` (never 0) when evidence is unavailable; no fake
  measurements are generated.

## Quality gating (feature-specific)

- Primary outcomes and control factors are gated PER FEATURE, not all or
  nothing. Gating is based on the engineering visibility threshold
  `config.MIN_LANDMARK_VISIBILITY` (not a clinical threshold).
- A landmark is available when present, finite (x/y/z/visibility not
  NaN/±inf), and above the visibility threshold.
- Examples: a missing left wrist does not erase valid knee primary outcomes
  (only wrist-based control factors become `None`); a missing left ankle
  makes only the LEFT knee primary outcome `None` while the right knee and
  unrelated control factors stay valid.
- `quality["available"]` means BOTH primary knee outcomes are available.
  Additional flags expose per-side availability, completeness, and the
  missing/low-quality landmark list (see `FrameEvidence`).

## CF mapping (Control Factors)

| KIMORE concept | BioGait implementation | Classification |
|----------------|------------------------|----------------|
| Hand distance | wrist-to-wrist Euclidean 3D distance (wrist = Hand proxy) | ENGINEERING_ADAPTED |
| Shoulder width | shoulder-to-shoulder Euclidean 3D distance | ENGINEERING_ADAPTED |
| Hip width | hip-to-hip Euclidean 3D distance | ENGINEERING_ADAPTED |
| Knee width (paper d_k) | The KIMORE PAPER labels d_k as knee distance, but the reviewed feature-extraction source computes a SIGNED Y-coordinate difference (`deltayknee = Knee_R(:,2) - Knee_L(:,2)`). BioGait implements `knee_delta_y_m = right_knee.y - left_knee.y` and preserves this discrepancy in provenance rather than silently equating the two. The Euclidean `knee_euclidean_3d_m` is a separate DESCRIPTIVE value and is NOT presented as the source d_k | REFERENCE_DERIVED equation + ENGINEERING_ADAPTED coordinate transfer (knee_delta_y_m); DESCRIPTIVE / ENGINEERING_ADAPTED (knee_euclidean_3d_m) |
| Ankle width | ankle-to-ankle Euclidean 3D distance | ENGINEERING_ADAPTED |
| Hand-shoulder distance | left/right wrist-to-shoulder Euclidean 3D distances | ENGINEERING_ADAPTED |
| Torso area | quadrilateral LS-RS-RH-LH decomposed into two Heron triangles | ENGINEERING_ADAPTED |
| Shoulder transverse-plane coordinates | raw per-frame left/right shoulder X/Z world coordinates captured; the paper describes zero-mean normalization, which is implemented only as an offline helper (`center_sequence`) — full source-style zero-mean CF temporal preprocessing on the live frame evidence is NOT claimed | ENGINEERING_ADAPTED (raw capture) / DEFERRED (full CF temporal preprocessing) |

> **CF temporal preprocessing is DEFERRED.** The reviewed source later discards
> the last 15 samples from several CF streams and applies filtering to CF
> streams. Sprint A implements CF geometry/evidence only — that later CF
> temporal trim/filter preprocessing has not been reproduced and is not
> claimed.

## Filtering

Three separate filter paths (never interchangeable):

- **Reference (offline, non-causal):** Butterworth order 3, cutoff 1 Hz,
  FIXED 30 Hz reference sample rate — `[b, a] = butter(order=3, cutoff=1 Hz,
  fs=30 Hz)` + `filtfilt(b, a, x)`. Parameters are not caller-redefinable;
  input must be a complete finite sequence (None/NaN/+-inf raise ValueError).
  Classification: REFERENCE_DERIVED / OFFLINE ONLY / NON-CAUSAL. The
  source-aligned reference path only runs on a complete stream at 30 Hz with
  uniform 30 Hz timestamps.
- **Adapted (offline, non-causal):** `kimore_adapted_zero_phase_filter(values,
  fs)` — order 3, 1 Hz at the ACTUAL supplied frame rate. Classification:
  ENGINEERING_ADAPTED. NOT the reference filter; results must never be
  labelled REFERENCE_DERIVED.
- **Causal adaptation:** `CausalKimoreButterworth` — stateful SOS filtering.
  Classification: ENGINEERING_ADAPTED. Not `filtfilt`-equivalent, introduces
  phase delay, not clinically validated; causal output does not equal either
  zero-phase output.

## Source-aligned reference temporal analysis

Offline reference path describing the KIMORE Ex5 event-extraction convention:

1. KIMORE source retains samples `10:end` in MATLAB (1-based) indexing —
   equivalent to discarding the first 9 samples (`values[9:]`) in zero-based
   Python; trimmed index 0 maps to original Python index 9 / MATLAB sample
   10;
2. exact sign-flip correction (negate a sample when the consecutive angle
   difference is below −100° or above +100° — NOT a ±360 unwrap);
3. ba-form `filtfilt` reference filter (FIXED 30 Hz, order 3, 1 Hz);
4. maxima at `max(signal)/√2`;
5. minima on `max(signal) − signal` at `max(transformed)/√2`;
6. minimum peak distance `⌊n/10⌋`.

- The algorithmic conventions and parameters follow the reviewed KIMORE
  source. Numerical identity with the original MATLAB runtime has not been
  established — this is a **source-aligned reference implementation**, not a
  claim of sample-for-sample EXACT reproduction.
- The source-aligned reference path requires a complete (no missing samples)
  stream at the 30 Hz reference convention, and when timestamps are supplied
  they must be finite, strictly increasing, and uniform at 30 Hz. Violations
  return a structured warning (`missing_samples_require_resampling`,
  `reference_requires_30hz_or_resampling`, or
  `reference_requires_uniform_30hz_timestamps_or_resampling`) and no
  filtering/peak detection runs.
- An ENGINEERING_ADAPTED path at the video's actual frame rate is also
  reported and is never labelled REFERENCE_DERIVED; its timestamps must be
  uniform at the supplied rate.
- Event `time_s` refers to the original source-session timeline (derived as
  `original_index / fs` when timestamps are absent, or the supplied timestamp
  when present) — never restarted at zero after the initial trim.
- Detected events are **candidate** repetition events — **not** clinically
  valid repetitions — and the path produces no pass/fail.
- The KIMORE acquisition protocol involved repeated exercise execution; its
  full-sequence peak settings are **not automatically valid** for an
  arbitrary live session length.

Classification: REFERENCE_DERIVED / OFFLINE / NOT REALTIME.

## Temporal-export and descriptive metrics

- Session export (`temporal_analysis`) keeps SEPARATE provenance branches:
  - `reference` (REFERENCE_DERIVED): per-side analysis + per-side maxima
    counts/durations, bilateral pairing deferred
    (`bilateral_pairing_status: "deferred"`), no combined/union repetition
    count.
  - `adapted` (ENGINEERING_ADAPTED): the same structure using the actual
    frame rate. Descriptive session metrics NEVER carry adapted event counts
    under "reference" names.
- Pure descriptive session descriptors: session duration, effective sample
  rate, left/right knee ROM, left/right peak & mean absolute angular velocity
  (finite difference Δangle/Δt; intervals with a missing angle or
  non-increasing timestamp are skipped — gaps are never bridged), and
  left-right ROM difference.
- Offline analysis assumes a constant frame rate
  (`timing_model: constant_frame_rate_from_fps`) from video FPS metadata or an
  explicit `--fps` override; variable-frame-rate inputs should be
  transcoded/resampled to a constant frame rate before scientific temporal
  comparison, and no claim of true per-frame source PTS recovery is made.

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
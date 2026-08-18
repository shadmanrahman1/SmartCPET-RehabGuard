# Evidence

This directory documents the evidence base for every clinical, physiological, or movement-analysis metric in SmartCPET-RehabGuard.

> **Do NOT fill unsupported details.** If a field is unknown, write "TBD" or "Pending".
> See `AGENTS.md` for the full evidence policy.

---

## Implementation Evidence Table Template

Copy the row template below for each new metric. Delete rows that are not yet applicable.

| Field | Description |
|-------|-------------|
| **Component** | Name of the metric, module, or feature |
| **Paper** | Citation (DOI / PubMed / arXiv link) |
| **Dataset** | Dataset used (if any) |
| **Clinical label** | What clinical concept it represents |
| **Input** | Variables the method uses |
| **Equation / method** | Mathematical formulation or algorithm |
| **Official/author code** | Link to reference implementation (if any) |
| **Our decision** | USE / ADAPT / SKIP |
| **Adaptation notes** | What was changed, if ADAPT; why, if SKIP |
| **Implementation file** | Path to the implementation in this repo |
| **Validation status** | None / Internal only / Externally validated / Clinically validated |

---

## CPET Module

(TBD — to be filled as evidence-based methodology milestones are completed.)

## BioGait Module

> The current legacy risk scoring is a rule-based experimental screening
> baseline and is **not** clinically validated. New research metrics are
> KIMORE-informed and descriptive; they are not clinical scores.

See `evidence/kimore-ex5-squat.md` for the Exercise-5 (squat) research row.

### Evidence rows

| Component | Paper | Dataset | Clinical label | Input | Equation / method | Reference code | Decision | Adaptation notes | Implementation | Validation |
|-----------|-------|---------|----------------|-------|-------------------|----------------|----------|------------------|----------------|------------|
| Sagittal knee angle (KIMORE Exercise 5) | Capecci et al. 2019, DOI 10.1109/TNSRE.2019.2923060 | KIMORE | None claimed (descriptive kinematics) | MediaPipe world hip/knee/ankle | Source-aligned reviewed Ex5 convention `degrees(atan2(hip_y-knee_y, hip_z-knee_z) + atan2(knee_y-ankle_y, ankle_z-knee_z))`; NOT a clamped 0..180 acos angle; degenerate segments -> None; numerical identity with the original MATLAB runtime not established | `matlab_original/feat_extract_Ex5.m` | ADAPT | Adapted from Kinect RGB-D to monocular-RGB MediaPipe world landmarks; engineering-adapted coordinate transfer, no numerical equivalence assumed; equation follows the reviewed source | `biogait/evidence_features.py` | None (ENGINEERING_ADAPTED transfer / REFERENCE_DERIVED equation) |
| Control factors (wrist/shoulder/hip/ankle distances + shoulder x/z) | Capecci et al. 2019, DOI 10.1109/TNSRE.2019.2923060 | KIMORE | None claimed | MediaPipe world landmarks | Euclidean 3D distances; shoulder coordinates captured raw per frame (source-style zero-mean CF preprocessing DEFERRED) | `matlab_original/feat_extract_Ex5.m` | ADAPT | MediaPipe WRIST is a proxy for the KIMORE Hand joint (not exact equivalent); feature-specific quality gating via config.MIN_LANDMARK_VISIBILITY | `biogait/evidence_features.py` | None (ENGINEERING_ADAPTED) |
| Knee width CF (paper d_k vs source) | Capecci et al. 2019, DOI 10.1109/TNSRE.2019.2923060 | KIMORE | None claimed | MediaPipe left/right knee | Paper labels d_k as knee distance; reviewed source computes `deltayknee = Knee_R(:,2) - Knee_L(:,2)` (signed Y difference) → `knee_delta_y_m`; `knee_euclidean_3d_m` is a separate DESCRIPTIVE Euclidean value NOT presented as source d_k | `matlab_original/feat_extract_Ex5.m` | ADAPT | Discrepancy preserved in provenance rather than silently equated | `biogait/evidence_features.py` | None (REFERENCE_DERIVED equation + ENGINEERING_ADAPTED transfer; DESCRIPTIVE for knee_euclidean_3d_m) |
| Torso area | Capecci et al. 2019, DOI 10.1109/TNSRE.2019.2923060 | KIMORE | None claimed | MediaPipe world shoulders/hips | Two-triangle Heron decomposition of the shoulder-hip quadrilateral | `matlab_original/feat_extract_Ex5.m` | ADAPT | Monocular-RGB world coordinates; degenerate geometry → 0.0 m² | `biogait/evidence_features.py` | None (ENGINEERING_ADAPTED) |
| Reference zero-phase temporal filter | Capecci et al. 2019 (KIMORE wrapper `filtering.m`) | KIMORE | None claimed | Knee-angle stream | Butterworth order 3, 1 Hz cutoff, FIXED 30 Hz reference rate; ba-form (`butter`) + `filtfilt` (non-causal); FIXED parameters (not caller-redefinable); rejects None/NaN/±inf | `matlab_original/filtering.m` | ADAPT | Offline only; must not be used as realtime causal filter; requires complete finite stream at 30 Hz | `biogait/temporal_filters.py` | None (REFERENCE_DERIVED / OFFLINE) |
| Adapted zero-phase filter | Capecci et al. 2019 (concept) | KIMORE | None claimed | Knee-angle stream + actual fs | Butterworth order 3, 1 Hz at the caller-supplied actual frame rate; ba-form + `filtfilt`, non-causal | `filtering.m` (adapted) | ADAPT | NOT the reference filter; results must never be labelled REFERENCE_DERIVED; rejects None/NaN/±inf | `biogait/temporal_filters.py` | None (ENGINEERING_ADAPTED) |
| Causal Butterworth adaptation | Capecci et al. 2019 (concept) | KIMORE | None claimed | Knee-angle stream + sampling rate | Causal stateful SOS Butterworth order 3, 1 Hz | `filtering.m` (adapted) | ADAPT | Not `filtfilt`-equivalent; phase delay; not clinically validated; causal output does not equal either zero-phase output | `biogait/temporal_filters.py` | None (ENGINEERING_ADAPTED) |
| Source-aligned reference temporal analysis (Ex5) | Capecci et al. 2019 (KIMORE wrapper `feat_extract_Ex5.m`) | KIMORE | None claimed (events are candidates only) | Filtered knee-angle stream | Requires complete stream at 30 Hz + finite, strictly increasing, uniform 30 Hz timestamps; MATLAB `10:end` trim (discard first 9 in zero-based Python); sign-flip when consecutive diff outside [-100,+100] (NOT ±360 unwrap); ba-form `filtfilt`; maxima/minima at max/√2; min peak distance ⌊n/10⌋; event time_s on the original source-session timeline | `matlab_original/feat_extract_Ex5.m` | ADAPT | Source-aligned reference implementation (numerical identity with MATLAB runtime not established); candidates are not clinically valid repetitions; reference gate refuses non-30 Hz/29.97 sources | `biogait/reference_temporal.py` | None (REFERENCE_DERIVED / OFFLINE) |
| Adapted temporal analysis (Ex5) | Capecci et al. 2019 (concept) | KIMORE | None claimed | Filtered knee-angle stream + actual fs | Same pipeline structure at the actual frame rate via the adapted zero-phase filter; timestamps must be uniform at the supplied rate | `matlab_original/feat_extract_Ex5.m` (concept) | ADAPT | ENGINEERING_ADAPTED; never REFERENCE_DERIVED; per-side summary under the adapted provenance branch only | `biogait/reference_temporal.py` | None (ENGINEERING_ADAPTED) |
| Descriptive ROM / angular velocity | — (descriptive math) | — | None claimed | Valid knee-angle + time streams | max−min; finite-difference Δangle/Δtime; absolute peak/mean | — | USE | Descriptive kinematics only; not a clinical score; index-aligned gaps skipped | `biogait/session_analysis.py` | None (DESCRIPTIVE) |

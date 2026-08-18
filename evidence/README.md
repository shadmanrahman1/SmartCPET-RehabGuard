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
| Sagittal knee angle (KIMORE Exercise 5) | Capecci et al. 2019, DOI 10.1109/TNSRE.2019.2923060 | KIMORE | None claimed (descriptive kinematics) | MediaPipe world hip/knee/ankle | Exact reviewed Ex5 convention `degrees(atan2(hip_y-knee_y, hip_z-knee_z) + atan2(knee_y-ankle_y, ankle_z-knee_z))`; NOT a clamped 0..180 acos angle; degenerate segments -> None | `matlab_original/feat_extract_Ex5.m` | ADAPT | Adapted from Kinect RGB-D to monocular-RGB MediaPipe world landmarks; engineering-adapted coordinate transfer, no numerical equivalence assumed; equation follows the reviewed source | `biogait/evidence_features.py` | None (ENGINEERING_ADAPTED transfer / REFERENCE_DERIVED equation) |
| Control factors (wrist/shoulder/hip/knee/ankle distances) | Capecci et al. 2019, DOI 10.1109/TNSRE.2019.2923060 | KIMORE | None claimed | MediaPipe world landmarks | Euclidean 3D distances | `matlab_original/feat_extract_Ex5.m` | ADAPT | MediaPipe WRIST is a proxy for the KIMORE Hand joint (not exact equivalent) | `biogait/evidence_features.py` | None (ENGINEERING_ADAPTED) |
| Torso area | Capecci et al. 2019, DOI 10.1109/TNSRE.2019.2923060 | KIMORE | None claimed | MediaPipe world shoulders/hips | Two-triangle Heron decomposition of the shoulder-hip quadrilateral | `matlab_original/feat_extract_Ex5.m` | ADAPT | Monocular-RGB world coordinates; degenerate geometry → 0.0 m² | `biogait/evidence_features.py` | None (ENGINEERING_ADAPTED) |
| Reference zero-phase temporal filter | Capecci et al. 2019 (KIMORE wrapper `filtering.m`) | KIMORE | None claimed | Knee-angle stream | Butterworth order 3, 1 Hz cutoff, 30 Hz reference rate; ba-form (`butter`) + `filtfilt` (non-causal) | `matlab_original/filtering.m` | ADAPT | Offline only; must not be used as realtime causal filter; requires 30 Hz convention | `biogait/temporal_filters.py` | None (REFERENCE_DERIVED / OFFLINE) |
| Causal Butterworth adaptation | Capecci et al. 2019 (concept) | KIMORE | None claimed | Knee-angle stream + sampling rate | Causal stateful SOS Butterworth order 3, 1 Hz | `filtering.m` (adapted) | ADAPT | Not `filtfilt`-equivalent; phase delay; not clinically validated; causal output does not equal reference output | `biogait/temporal_filters.py` | None (ENGINEERING_ADAPTED) |
| Reference temporal analysis (Ex5) — EXACT | Capecci et al. 2019 (KIMORE wrapper `feat_extract_Ex5.m`) | KIMORE | None claimed (events are candidates only) | Filtered knee-angle stream | Requires complete stream at 30 Hz; MATLAB `10:end` trim (discard first 9 in zero-based Python); sign-flip when consecutive diff >100° (FAILS ±360 unwrap); ba-form `filtfilt`; maxima/minima at max/√2; min peak distance ⌊n/10⌋ | `matlab_original/feat_extract_Ex5.m` | ADAPT | Offline reference path; candidates are not clinically valid repetitions; peak settings not valid for arbitrary session length | `biogait/reference_temporal.py` | None (REFERENCE_DERIVED / OFFLINE) |
| Descriptive ROM / angular velocity | — (descriptive math) | — | None claimed | Valid knee-angle + time streams | max−min; finite-difference Δangle/Δtime; absolute peak/mean | — | USE | Descriptive kinematics only; not a clinical score | `biogait/session_analysis.py` | None (DESCRIPTIVE) |

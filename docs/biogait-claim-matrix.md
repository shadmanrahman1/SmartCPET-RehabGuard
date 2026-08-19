# BioGait Claim Matrix (Sprint B)

This matrix records what BioGait may and may not claim in papers, PRs, and
documentation. It is a provenance guard — not a measurement.

| Claim | Evidence | Experiment | Current status | Allowed wording | Forbidden wording |
|-------|----------|------------|----------------|------------------|-------------------|
| Source-aligned KIMORE-informed feature extraction | Reviewed KIMORE paper + KiMoRe_wrapper scripts; Python re-implementation | Direct KIMORE Ex5 source-skeleton evaluator (B5) | Tooling completed; real-data validation PENDING | "source-aligned KIMORE-informed feature extraction" | "clinically validated rehabilitation score" |
| Sagittal knee angle follows the reviewed atan2 equation | Capecci et al. 2019 + `feat_extract_Ex5.m` | Geometry unit tests (A) | COMPLETE (unit); numerical identity with MATLAB runtime NOT established | "the reviewed atan2 equation is source-derived" | "numerically identical to MATLAB output" |
| Reference temporal path is source-aligned | Reviewed scripts `filtering.m` / `feat_extract_Ex5.m` | Reference-analysis unit tests (A) | COMPLETE (unit) | "source-aligned KIMORE reference path" | "EXACT KIMORE reproduction", "sample-for-sample identical" |
| Feature-specific quality gating | Feature requirements + `config.MIN_LANDMARK_VISIBILITY` | Landmark robustness matrix (B9) | COMPLETE (synthetic) | "engineering visibility threshold (not clinical)" | "patient-specific clinical quality score" |
| MediaPipe world-landmark representation | MediaPipe docs, monocular-RGB inference | — | ENGINEERING_ADAPTED | "engineering-adapted MediaPipe world-landmark representation" | "equivalent to Kinect" |
| Candidate temporal events | Reference temporal analysis | FPS/missingness sensitivity (B7/B8) | COMPLETE (synthetic) | "candidate temporal events" | "clinically validated repetitions" |
| Runtime measured on X hardware/video | benchmark_video / benchmark_batch (B11) | Real video benchmark | PENDING (no real video) | "runtime measured on X hardware/video" (ONLY when actual measurement exists) | any runtime number without a real measurement |
| KIMORE paper/source knee-CF discrepancy preserved | Paper vs `deltayknee = Knee_R(:,2) - Knee_L(:,2)` | Mapping report (B6) | COMPLETE | "BioGait preserves the paper/source discrepancy in provenance" | "BioGait reproduces the paper's d_k as a Euclidean distance" |
| No clinical score, no pass/fail, no prediction of cPO/cCF/cTS | Scope policy | — | POLICY | "descriptive / source-aligned; no clinical score" | "clinical score", "correct squat", "incorrect squat", "diagnostic", "rehabilitation-quality judgement" |
| MediaPipe-vs-Kinect numerical validation | — | — | DEFERRED | (not claimed) | "MediaPipe correlates with Kinect", "gold standard" |

## Forbidden-wording audit

Search targets (B23): `clinically validated`, `diagnostic`, `correct squat`,
`incorrect squat`, `Kinect-equivalent`, `clinical score`, `gold standard`.
Any occurrence in BioGait changed files must be a negation/limitation or
removed.

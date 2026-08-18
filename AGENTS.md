# AGENTS.md — Coding Agent and Evidence Policy

This file establishes rules for any coding agent (human or AI) that works on this repository. It exists to preserve scientific integrity, reproducibility, and the legacy-baseline boundary.

---

## Hard Rules

1. **Do NOT invent clinical thresholds.** Numerical thresholds for clinical or physiological interpretation must come from a cited evidence source. Engineering heuristics (e.g. for UI warnings) must be clearly distinguished from clinical thresholds.

2. **Do NOT invent clinical validation claims.** If the existing documentation does not state a validation result, do not add one. If a paper or dataset supports a claim, cite it explicitly.

3. **Distinguish method provenance.** Every new rehabilitation metric or analytical method must be labeled as one of:
   - **REFERENCE-DERIVED** — directly adapted from a published clinical reference or validated study
   - **ENGINEERING-ADAPTED** — modified from a published method to fit engineering constraints (note what was changed and why)
   - **EXPLORATORY** — not based on a published clinical method; clearly experimental

4. **Preserve legacy baselines.** The current BioGait risk scoring is a legacy rule-based experimental screening baseline and is NOT clinically validated. Do not silently replace it with a new method. Changes must be explicit and milestone-controlled.

5. **Preserve the primary BioGait runtime.** `app_qt.py` + `ui_worker.py` + PyQt5 dashboard are the conference-primary BioGait runtime. Do not remove or refactor them unless a specific milestone explicitly authorizes it.

6. **Do NOT commit secrets or private data.** API keys, tokens, patient data, raw biomedical recordings, and restricted datasets must never enter the repository.

7. **Do NOT silently change equations.** Any change to mathematical formulas, thresholds, or scoring weights must be documented in the relevant evidence file with a clear diff and justification.

8. **Research methods are milestone-controlled.** KIMORE-style methodology, temporal smoothing, ML model additions (XGBoost / TCN / MedGemma), and CPET-BioGait runtime merging are gated to future milestones. Do not implement them inline.

---

## Evidence Documentation

Every new clinical, physiological, or movement-analysis metric must have a row in `evidence/README.md` with:

- Component name
- Reference paper / source
- Dataset
- Clinical label (if applicable)
- Input variables
- Equation / method
- Official author code (if available)
- Our decision (USE / ADAPT / SKIP)
- Adaptation notes
- Implementation file
- Validation status

Do NOT fill unsupported details. If a field is unknown, write "TBD" or "Pending".

---

## Current BioGait Risk Scoring — Status

- **Type:** Engineering heuristic, legacy experimental screening baseline
- **Validation:** None (not clinically validated)
- **Status:** Frozen as a legacy baseline until explicitly replaced by an evidence-driven milestone

Do not present this scoring as clinical evidence. Do not present its thresholds as medically correct.

---

## Current Model Artifacts

| Model | Status |
|-------|--------|
| `arrhythmia_cnn_final.keras` | Project-trained, MIT-BIH data; bundled raw dataset NOT included; no independent clinical validation claim |
| `best_arrhythmia_model.keras` | Backup, same provenance |
| `pose_landmarker_lite.task` | Pretrained MediaPipe asset; pose landmark extraction only — NOT a rehabilitation-quality model |

See `docs/model-provenance.md` for full provenance details.

---

## What NOT to Do in This Repo

- ❌ Replace current thresholds with "more sensible" values without evidence
- ❌ Add new metrics that are not cited to a published method
- ❌ Mark exploratory metrics as "validated"
- ❌ Modify `metrics.py` equations except as part of an evidence-controlled milestone
- ❌ Commit `.env.local`, API keys, raw MIT-BIH data, patient data, or screenshots
- ❌ Implement smoothing, ML models, KIMORE, or MedGemma integration outside an approved milestone
- ❌ Merge CPET and BioGait runtime code in this milestone

---

## Reference

- `THIRD_PARTY_NOTICES.md` — third-party dependency licensing
- `docs/model-provenance.md` — model origin and training data
- `evidence/README.md` — evidence table template
- `docs/current-state/` — current implementation documentation

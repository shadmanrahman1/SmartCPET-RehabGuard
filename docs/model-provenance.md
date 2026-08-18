# Model Provenance

This document records the origin, training data, and current validation status of all model artifacts included in this repository. No accuracy or validation claims are made beyond what the original project evidence already supports.

---

## A. `cpet/backend/arrhythmia_cnn_final.keras`

| Attribute | Value |
|-----------|-------|
| **Type** | 1D Convolutional Neural Network (CNN) |
| **Framework** | TensorFlow / Keras |
| **Output** | 5-class beat classification (AAMI-style mapping) |
| **Class mapping** | See table below |
| **Training data** | MIT-BIH Arrhythmia Database — PhysioNet, DOI: 10.13026/C2F305, licensed under Open Data Commons Attribution License v1.0 (ODC-By 1.0) |
| **Training data bundled?** | **No** — raw MIT-BIH data is not redistributed in this repo |
| **Training notebook** | `cpet/backend/Arrythmia with MIT-BIH.ipynb` (included) |
| **Inference rate** | ~360 Hz (project-reported) |
| **Current validation claims** | Only what the existing project documents state |

**Class mapping (verified from `cpet/backend/main.py` and `cpet/web_dashboard/src/lib/ecg-config.ts`):**

| Class index | Name | Severity |
|-------------|------|----------|
| 0 | Normal | low |
| 1 | Supraventricular | medium |
| 2 | Ventricular | high |
| 3 | Fusion | medium |
| 4 | Unknown/Paced | low |

**Notes:**
- The model is a project-trained artifact.
- MIT-BIH redistribution compliance is the user's responsibility.
- No independent clinical validation is claimed.

---

## B. `cpet/backend/best_arrhythmia_model.keras`

| Attribute | Value |
|-----------|-------|
| **Type** | Backup/alternative CNN |
| **Training data** | MIT-BIH Arrhythmia Database — PhysioNet, DOI: 10.13026/C2F305, ODC-By 1.0 (same provenance as A) |
| **Training data bundled?** | **No** |
| **Current status** | Backup artifact |

**Notes:**
- Same provenance caveat as `arrhythmia_cnn_final.keras`.
- The two files appear nearly identical in size; the relationship between them is not externally documented.

---

## C. `biogait/pose_landmarker_lite.task`

| Attribute | Value |
|-----------|-------|
| **Type** | MediaPipe Pose Landmarker (float16) |
| **Source** | Google MediaPipe official release |
| **Download URL** | `https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task` |
| **Auto-download** | Yes — `biogait/ui_worker.py:_ensure_model()` |
| **License:**
  - **MediaPipe framework / Python package:** Apache License 2.0
  - **PoseLandmarker model artifact** (`pose_landmarker_lite.task`): Official Google-hosted pretrained model asset. Model artifact redistribution/license terms: **pending explicit verification**.
| **Use** | Pose landmark extraction only |

**Notes:**
- This is a **general-purpose pretrained pose model**. It is **not** a rehabilitation-quality model.
- It performs landmark detection only. Clinical-grade rehabilitation metrics require a separate validated model.
- See `THIRD_PARTY_NOTICES.md` for license details.

---

## General Notes

- No accuracy numbers, sensitivity, or specificity are reported in this document beyond what the original project documentation already states.
- Adding new metrics, changing thresholds, or retraining models requires evidence-based validation per `AGENTS.md`.
- All model artifacts are provided "as-is" for research prototype purposes.

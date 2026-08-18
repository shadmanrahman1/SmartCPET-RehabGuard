# Third-Party Notices

This document lists third-party software and data used by SmartCPET-RehabGuard. Each dependency is governed by its own license; users must comply with those licenses separately.

---

## MediaPipe / Google AI Edge

- **Component:** PoseLandmarker model (`biogait/pose_landmarker_lite.task`)
- **Source:** https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task
- **Governing License:**
  - **MediaPipe framework / Python package:** Apache License 2.0
  - **PoseLandmarker model artifact** (`pose_landmarker_lite.task`): Official Google-hosted pretrained model asset. Model artifact redistribution/license terms: **pending explicit verification**. Users must verify the model artifact license directly with Google before any redistribution.
- **Use:** Pose landmark extraction only. Not used for any clinical decision-making.
- **Not a rehabilitation-quality model.** This is a general-purpose pretrained pose model.

---

## MIT-BIH Arrhythmia Database

- **Component:** Training dataset for `cpet/backend/arrhythmia_cnn_final.keras` and `cpet/backend/best_arrhythmia_model.keras`
- **Name:** MIT-BIH Arrhythmia Database
- **Source:** PhysioNet
- **DOI:** 10.13026/C2F305
- **URL:** https://physionet.org/content/mitdb/1.0.0/
- **License:** Open Data Commons Attribution License v1.0 (ODC-By 1.0)
- **Bundled status:** Raw MIT-BIH distribution files are **not bundled** in this repository. Only trained model weights derived from the dataset are included.

**Attribution statement:**

> The arrhythmia CNN model weights included in this repository (`arrhythmia_cnn_final.keras`, `best_arrhythmia_model.keras`) were derived from the MIT-BIH Arrhythmia Database distributed by PhysioNet (DOI: 10.13026/C2F305), licensed under ODC-By 1.0. The authors gratefully acknowledge PhysioNet and the original contributors of the MIT-BIH Arrhythmia Database.

If you intend to retrain the CNN model, obtain the dataset directly from PhysioNet and comply with the ODC-By 1.0 attribution requirements.

---

## TensorFlow / Keras

- **Component:** CNN arrhythmia classifier framework
- **License:** Apache License 2.0
- **Use:** Training and inference of the 5-class arrhythmia model.

---

## Next.js

- **Component:** `cpet/web_dashboard` (CPET monitoring UI)
- **License:** MIT License
- **Source:** https://nextjs.org/

---

## FastAPI

- **Component:** `cpet/backend/main.py` (CPET API server)
- **License:** MIT License
- **Source:** https://fastapi.tiangolo.com/

---

## OpenCV

- **Component:** Image capture and processing
- **License:** Apache License 2.0

---

## Streamlit

- **Component:** `biogait/dashboard.py` (legacy BioGait dashboard)
- **License:** Apache License 2.0

---

## PyQt5

- **Component:** `biogait/app_qt.py`, `biogait/ui_widgets.py`, `biogait/ui_worker.py` (primary BioGait runtime)
- **License:** PyQt5 is dual-licensed by Riverbank Computing Limited under:
  - **GNU General Public License (GPL) v3**, or
  - **Riverbank Commercial License**
- **Note:** The choice between these two licenses must be made by the application author/distributor. Merely being a research prototype does not automatically resolve GPL obligations. The final repository/application licensing must be compatible with the applicable PyQt license, or an appropriate Riverbank Commercial License must be obtained.
- **Reference:** https://www.riverbankcomputing.com/software/pyqt/

---

## OpenRouter API

- **Component:** `cpet/web_dashboard/src/app/api/generate-report/route.ts`
- **Use:** External API for AI-assisted research/decision-support summaries
- **Note:** Requires user-supplied API key. Not bundled with this repository.
- **Data handling:** Patient data is sent to OpenRouter at runtime if user configures the integration. Users must review OpenRouter's data policy before use.

---

## Appwrite

- **Component:** `cpet/web_dashboard/src/lib/appwrite.ts`, `cpet/web_dashboard/setup-appwrite.example.js`
- **Use:** Optional patient database backend (user-configured)
- **License:** BSD-3-Clause
- **Note:** Requires user-supplied endpoint and credentials. Not bundled.

---

## Disclaimer

The project owners are not legal advisors. This document is informational. All third-party components must be independently verified for license compatibility before redistribution or commercial use.

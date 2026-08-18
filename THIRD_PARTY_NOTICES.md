# Third-Party Notices

This document lists third-party software and data used by SmartCPET-RehabGuard. Each dependency is governed by its own license; users must comply with those licenses separately.

---

## MediaPipe / Google AI Edge

- **Component:** PoseLandmarker model (`biogait/pose_landmarker_lite.task`)
- **Source:** https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task
- **Governing License:** Apache License 2.0 (MediaPipe framework)
- **Use:** Pose landmark extraction only. Not used for any clinical decision-making.
- **Not a rehabilitation-quality model.** This is a general-purpose pretrained pose model.

The MediaPipe Python package (`mediapipe`) is distributed under the Apache License 2.0.

---

## MIT-BIH Arrhythmia Database

- **Component:** Training dataset for `cpet/backend/arrhythmia_cnn_final.keras` and `cpet/backend/best_arrhythmia_model.keras`
- **Source:** MIT-BIH Arrhythmia Database, PhysioNet
- **URL:** https://physionet.org/content/mitdb/1.0.0/
- **Access:** Free for research and educational use; redistribution requires PhysioNet policy compliance.
- **Bundled status:** Raw MIT-BIH distribution files are **not bundled** in this repository. Only trained model weights derived from the dataset are included.

If you intend to retrain the CNN model, obtain the dataset directly from PhysioNet and comply with their redistribution policy.

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
- **License:** GPL v3 / Riverbank Commercial License
- **Note:** PyQt5 is dual-licensed. For open-source research prototypes, GPL applies. Commercial deployment requires a commercial license from Riverbank Computing.

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

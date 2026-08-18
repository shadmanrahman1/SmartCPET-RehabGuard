<div align="center">

# SmartCPET-RehabGuard

**Integrated Cardiopulmonary Exercise Testing + Movement Analysis Research Prototype**

[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)](https://python.org/)
[![Next.js](https://img.shields.io/badge/Next.js-16-black?logo=next.js)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-latest-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![MediaPipe](https://img.shields.io/badge/MediaPipe-Pose-FF6F00)](https://google.github.io/mediapipe/)
[![KUET](https://img.shields.io/badge/Research-KUET_BME-red)](https://kuet.ac.bd/)

</div>

---

> **Research prototype** — screening and decision-support architecture.
> **Not a clinical diagnostic device.** Clinical and evidence-based methodology upgrades are under active development.
>
> BioGait risk scoring is a legacy rule-based experimental screening baseline and is **not clinically validated**.

---

## Overview

SmartCPET-RehabGuard is a dual-module research system developed at Khulna University of Engineering & Technology (KUET), Department of Biomedical Engineering.

| Module | Purpose | Key Technologies |
|--------|---------|-----------------|
| **CPET** (`cpet/`) | Cardiopulmonary exercise testing — real-time ECG, SpO₂, HRV, ventilatory efficiency | Arduino, Raspberry Pi, FastAPI, Socket.IO, Next.js, TensorFlow/Keras |
| **BioGait** (`biogait/`) | RGB camera-based movement analysis — pose landmarks, gait symmetry, screening | OpenCV, MediaPipe Pose, PyQt5 |

---

## Repository Structure

```text
SmartCPET-RehabGuard/
├── cpet/                    # Cardiopulmonary Exercise Testing system
│   ├── backend/             # FastAPI + Socket.IO server, ECG model
│   └── web_dashboard/       # Next.js real-time monitoring dashboard
├── biogait/                 # Camera-based movement analysis prototype
│   ├── app_qt.py            # Primary Qt desktop runtime
│   ├── ui_worker.py         # QThread camera + MediaPipe worker
│   ├── app.py               # Legacy OpenCV window + file logging
│   ├── dashboard.py         # Legacy Streamlit (reads app.py output)
│   └── metrics.py           # Biomechanical calculations
├── docs/                    # Current-state documentation
│   └── model-provenance.md  # Model training data + licensing
├── evidence/                # Research evidence (template)
├── experiments/             # Experimental code (placeholder)
├── tests/                   # Test suite
├── AGENTS.md                # Agent/evidence policy
├── THIRD_PARTY_NOTICES.md   # Third-party dependency notes
├── .env.example             # Environment variable template
└── README.md
```

---

## CPET Module — Physiological Monitoring

A tri-layer architecture for high-speed biosignal acquisition and visualization:

```text
Arduino Mega (360 Hz)  →  Raspberry Pi 4 (CNN inference)  →  Next.js Dashboard
    │                          │                                    │
ECG, SpO₂, IMU,          TensorFlow/Keras                   Live waveforms,
CO₂, Airflow              Arrhythmia model                   patient records
```

### Key Features
- Real-time 5-class arrhythmia detection (CNN trained on MIT-BIH)
- 5 clinical CPET parameters: LRC Ratio, SpO₂/HR, LF/HF, PTT, VE/VCO₂
- 2-minute screening test workflow
- Multi-sensor fusion: ECG, PPG/SpO₂, MPU6050 IMU, MQ-135 CO₂
- Mobile-responsive dark/light theme dashboard
- Optional Appwrite patient database integration
- AI-assisted research/decision-support summaries (OpenRouter)

### Quick Start
```bash
# Backend
cd cpet/backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend
cd cpet/web_dashboard
npm install
npm run dev
```

---

## BioGait Module — Movement Analysis

A camera-based prototype for real-time gait screening using MediaPipe pose estimation.

### Active Runtime

The primary conference runtime is the PyQt5 desktop application:

```bash
cd biogait
pip install -r requirements.txt
python app_qt.py    # primary: Qt desktop with live waveform + metrics
```

### Legacy Pipeline

`app.py` is a legacy OpenCV-based runtime that writes metrics to `latest_metrics.json` and CSV files.

`dashboard.py` is a legacy Streamlit companion that reads the JSON file produced by `app.py`. It is **not** currently fed by `app_qt.py`.

### Key Features
- Real-time pose landmark detection (MediaPipe PoseLandmarker)
- Knee angle, trunk lean, left-right asymmetry calculation
- Risk scoring (0–100) — **legacy rule-based heuristic, not clinically validated**
- IP camera and laptop webcam support
- Session metrics logging

### Key Evidence

- BioGait heuristic: legacy rule-based experimental screening baseline.
- See `docs/model-provenance.md` for model and dataset provenance.
- See `AGENTS.md` for evidence policy on future metrics.

---

## Environment Setup

1. Copy `.env.example` to `.env.local` (for Next.js) or set system environment variables
2. Fill in your specific configuration values
3. See `docs/current-state/` for detailed integration notes

---

## Hardware Requirements

### CPET Module
- Arduino Mega 2560
- Raspberry Pi 4 (4GB+)
- AD8232 ECG sensor
- MAX30102 SpO₂ sensor
- MPU-6050 IMU
- MQ-135 CO₂ sensors (×2)
- Thermistor (airflow)

### BioGait Module
- Laptop webcam or Android phone with IP camera app
- No specialized hardware required

---

## Documentation

- `docs/current-state/PROGRESS_REPORT.md` — full project status
- `docs/current-state/CURRENT_STATE_FRONTEND.md` — frontend architecture
- `docs/current-state/FRONTEND_TEAM_BACKEND_REPORT.md` — integration notes
- `docs/model-provenance.md` — model training data and licensing notes
- `cpet/CPET_PARAMETERS_GUIDE.md` — clinical parameter reference
- `cpet/QUICK_START.md` — 5-minute setup guide
- `AGENTS.md` — coding agent / evidence policy
- `THIRD_PARTY_NOTICES.md` — third-party dependency notes

---

## License

> Project licensing and third-party notices are being prepared for the research release.
> See `THIRD_PARTY_NOTICES.md` for current third-party dependency notes.
> External dependencies are governed by their own respective licenses.

---

<div align="center">
  <sub>Built at KUET BME · Cardiopulmonary + Movement Analysis Research</sub>
</div>

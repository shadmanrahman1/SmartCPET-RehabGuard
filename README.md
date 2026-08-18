<div align="center">

# SmartCPET-RehabGuard

**Integrated Cardiopulmonary Exercise Testing + Movement Analysis Research Prototype**

[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)](https://python.org/)
[![Next.js](https://img.shields.io/badge/Next.js-16-black?logo=next.js)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-latest-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![MediaPipe](https://img.shields.io/badge/MediaPipe-Pose-FF6F00)](https://google.github.io/mediapipe/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![KUET](https://img.shields.io/badge/Research-KUET_BME-red)](https://kuet.ac.bd/)

</div>

---

> **Research prototype** — screening and decision-support architecture.
> **Not a clinical diagnostic device.** Clinical and evidence-based methodology upgrades are under active development.

---

## Overview

SmartCPET-RehabGuard is a dual-module research system developed at Khulna University of Engineering & Technology (KUET), Department of Biomedical Engineering.

| Module | Purpose | Key Technologies |
|--------|---------|-----------------|
| **CPET** (`cpet/`) | Cardiopulmonary exercise testing — real-time ECG, SpO₂, HRV, ventilatory efficiency | Arduino, Raspberry Pi, FastAPI, Socket.IO, Next.js, TensorFlow/Keras |
| **BioGait** (`biogait/`) | RGB camera-based movement analysis — pose landmarks, gait symmetry, risk screening | OpenCV, MediaPipe Pose, Streamlit, PyQt5 |

---

## Repository Structure

```text
SmartCPET-RehabGuard/
├── cpet/                    # Cardiopulmonary Exercise Testing system
│   ├── backend/             # FastAPI + Socket.IO server, ECG model
│   └── web_dashboard/       # Next.js real-time monitoring dashboard
├── biogait/                 # Camera-based movement analysis prototype
├── docs/                    # Current-state documentation
├── evidence/                # Research evidence (placeholder)
├── experiments/             # Experimental code (placeholder)
├── tests/                   # Test suite (placeholder)
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
- Real-time 5-class arrhythmia detection (MIT-BIH trained CNN)
- 5 clinical CPET parameters: LRC Ratio, SpO₂/HR, LF/HF, PTT, VE/VCO₂
- 2-minute screening test workflow
- Multi-sensor fusion: ECG, PPG/SpO₂, MPU6050 IMU, MQ-135 CO₂
- Mobile-responsive dark/light theme dashboard
- Optional Appwrite patient database integration
- AI-assisted report generation (OpenRouter)

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

### Key Features
- Real-time pose landmark detection (MediaPipe PoseLandmarker)
- Knee angle, trunk lean, left-right asymmetry calculation
- Risk scoring (0–100) with LOW/MODERATE/HIGH classification
- IP camera and laptop webcam support
- Streamlit dashboard + PyQt5 desktop application
- Session metrics logging (CSV)

### Quick Start
```bash
cd biogait
pip install -r requirements.txt

# Webcam (default)
python app.py

# Or desktop app
python app_qt.py

# Dashboard (separate terminal)
streamlit run dashboard.py
```

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
- `cpet/CPET_PARAMETERS_GUIDE.md` — clinical parameter reference
- `cpet/QUICK_START.md` — 5-minute setup guide

---

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">
  <sub>Built at KUET BME · Cardiopulmonary + Movement Analysis Research</sub>
</div>

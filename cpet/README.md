<div align="center">

# 🫀 AI-Powered Portable Cardiopulmonary Exercise Testing (CPET) System

**An ultra-low-cost, portable CPET system** that bridges high-cost clinical equipment with low-cost IoT hardware,
delivering real-time arrhythmia detection, HRV analytics, and ventilatory efficiency metrics.

[![Next.js](https://img.shields.io/badge/Next.js-16.1-black?logo=next.js)](https://nextjs.org/)
[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)](https://python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-latest-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![KUET](https://img.shields.io/badge/Research-KUET_BME-red)](https://kuet.ac.bd/)

</div>

---

## 🏗️ System Architecture

A **Tri-Layer Architecture** built for high-speed biosignal acquisition and lag-free visualization:

```
┌──────────────────┐    Serial (USB)    ┌──────────────────┐    Socket.IO    ┌──────────────────┐
│  Arduino Mega    │ ────────────────▶  │  Raspberry Pi 4  │ ─────────────▶  │  Next.js Web     │
│  360 Hz Sampling │                    │  CNN Inference   │                 │  Dashboard       │
│  Multi-sensor    │                    │  FastAPI Server  │                 │  Live Waveforms  │
└──────────────────┘                    └──────────────────┘    REST API     └──────────────────┘
         ▲                                       ▲                                     │
   Biosensors                           AI Model (.keras)                     Browser / Tablet
 (ECG, SpO₂, IMU,                   Arrhythmia Classification              Real-time Patient View
  CO₂, Airflow)                        + Robust Parameters
```

---

## 📡 Hardware Stack

**Total BOM Cost: Highly affordable (a fraction of traditional clinical systems)**

| Component | Role | Arduino Mega Pin | Supply |
|-----------|------|-----------------|--------|
| **AD8232** | ECG / HRV waveform acquisition | A0 (Signal), D10/D11 (Lead-Off) | 3.3 V |
| **MAX30102** | SpO₂ & Pulse Rate (I²C) | 20 (SDA), 21 (SCL) | 3.3 V |
| **MPU-6050** | Motion / Exercise Intensity (I²C) | 20 (SDA), 21 (SCL) | 3.3 V |
| **MQ-135 × 2** | Ambient CO₂ vs. Exhaled CO₂ | A1, A2 | 5 V |
| **Thermistor** | Hot-wire airflow / respiratory rate | A3 | 5 V |

---

## 📊 Robust CPET Parameters

Beyond basic heart rate, the system computes **5 clinical metrics** in real time:

| Parameter | Clinical Meaning |
|-----------|-----------------|
| **LRC Ratio** | Balance between respiratory and cardiac cycle periods |
| **SpO₂ / HR** | Oxygen delivery efficiency — surrogate for Oxygen Pulse (V̇O₂/HR) |
| **LF/HF Ratio** | Autonomic nervous system balance via HRV frequency-domain analysis |
| **PTT (ms)** | Pulse Transit Time — cuffless blood pressure estimation (ECG→PPG delay) |
| **VE/VCO₂ Slope** | Ventilatory efficiency — key CPET marker for heart failure risk |

---

## 🤖 AI Model

- **Architecture:** 1D Convolutional Neural Network (CNN)
- **Dataset:** MIT-BIH Arrhythmia Database (110,000+ labelled beats)
- **Classes:** 5 (Normal, PVC, APC, Left/Right Bundle Branch Block)
- **Inference rate:** ~360 Hz (real-time beat classification)
- **Framework:** TensorFlow / Keras → `.keras` model

---

## 💻 Quick Start

### Prerequisites
- Raspberry Pi 4 (or any Linux/Windows machine) running Python 3.11+
- Node.js 20+, npm

### 1 — Backend (AI Inference + API Server)

```bash
git clone https://github.com/shadmanrahman1/CPET_system.git
cd CPET_system/backend

# Create & activate virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the FastAPI + Socket.IO server
python main.py
# Server runs at http://localhost:8000
```

### 2 — Web Dashboard (Next.js)

```bash
cd ../web_dashboard
npm install
npm run dev
# Dashboard at http://localhost:3000
```

---

## 📁 Project Structure

```
CPET_system/
├── backend/
│   ├── main.py                       # FastAPI + Socket.IO server, AI inference
│   ├── requirements.txt              # Python dependencies
│   ├── arrhythmia_cnn_final.keras    # Trained CNN model
│   └── test_api.py                   # API endpoint tests
│
├── web_dashboard/
│   ├── src/
│   │   ├── app/                      # Next.js App Router pages
│   │   │   ├── page.tsx              # Landing page (Spline 3D hero)
│   │   │   ├── dashboard/            # System status & stats
│   │   │   ├── ecg-monitor/          # Live ECG waveform + AI predictions
│   │   │   ├── patients/             # Patient management table
│   │   │   └── analysis/[id]/        # Per-session deep analysis
│   │   ├── components/
│   │   │   ├── ecg/                  # ECGWaveform, ECGStatisticsDisplay
│   │   │   ├── layout/               # Sidebar, Header, AppLayout
│   │   │   └── SplineScene.tsx       # 3D interactive landing hero
│   │   └── lib/
│   │       ├── api.ts                # REST API client
│   │       ├── useECGSocket.ts       # Socket.IO React hook
│   │       └── ecg-config.ts         # Channel / server config
│   └── package.json
│
├── CPET_PARAMETERS_GUIDE.md          # Clinical parameter reference
├── INTEGRATION_README.md             # Hardware integration guide
├── QUICK_START.md                    # 5-minute setup guide
└── set_cache_envs.ps1                # Windows cache path configuration
```

---

## 🖥️ Dashboard Pages

| Route | Description |
|-------|-------------|
| `/` | Full-screen landing page with interactive 3D Spline model |
| `/dashboard` | System status cards, session summary, activity charts |
| `/ecg-monitor` | Live ECG waveform at 360 Hz, real-time CNN predictions |
| `/patients` | Patient records with session history |
| `/analysis/[id]` | Deep per-session analysis with HRV and CPET metrics |

---

## 🏫 Research Context

Developed as a research prototype at **Khulna University of Engineering & Technology (KUET)**, Department of Biomedical Engineering.

The goal is to provide athletes and patients in **low-resource clinical settings** with access to high-fidelity cardiac monitoring that typically requires equipment costing 10–100× more.

Designed and built independently by **Shadman Rahman** (Biomedical Engineering, KUET).

---

## 📄 License

This project is licensed under the **MIT License** — see [`LICENSE`](LICENSE) for details.

---

<div align="center">
  <sub>Built with ❤️ at KUET BME · Powered by TensorFlow, FastAPI, Next.js & Spline</sub>
</div>

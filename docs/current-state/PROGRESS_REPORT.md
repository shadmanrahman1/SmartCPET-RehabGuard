# 🫀 CPET System — Project Progress Report

> **Author:** Shadman Rahman · KUET Biomedical Engineering  
> **Report Generated:** 2026-07-03  
> **Project:** AI-Powered Portable Cardiopulmonary Exercise Testing (CPET) System  
> **Repository:** [CPET_system](https://github.com/shadmanrahman1/CPET_system)

---

## 📋 Table of Contents

1. [Project Overview](#-project-overview)
2. [System Architecture](#-system-architecture)
3. [Hardware Stack Status](#-hardware-stack-status)
4. [Backend Status](#-backend-status)
5. [Frontend / Dashboard Status](#-frontend--dashboard-status)
6. [AI Model Status](#-ai-model-status)
7. [Integration Status](#-integration-status)
8. [Feature Completion Matrix](#-feature-completion-matrix)
9. [Known Issues & Blockers](#-known-issues--blockers)
10. [Pending Work & Next Steps](#-pending-work--next-steps)
11. [Security Checklist](#-security-checklist)
12. [Environment & Configuration](#-environment--configuration)

---

## 🧭 Project Overview

The CPET system is an **ultra-low-cost, portable Cardiopulmonary Exercise Testing** research prototype built at **Khulna University of Engineering & Technology (KUET)**, Department of Biomedical Engineering.

**Goal:** Deliver clinical-grade cardiac + pulmonary monitoring (arrhythmia detection, HRV analytics, ventilatory efficiency) using IoT hardware that costs a fraction of traditional clinical equipment.

**Key Technology Stack:**

| Layer | Technology |
|-------|-----------|
| Firmware | Arduino Mega (360 Hz multi-sensor sampling) |
| Edge Compute | Raspberry Pi 4 (CNN inference + Socket.IO server) |
| Backend API | Python · FastAPI · Uvicorn |
| Frontend | Next.js 16 (App Router) · TypeScript · Socket.IO client |
| AI Model | TensorFlow/Keras 1D-CNN · MIT-BIH Dataset |
| Database | Appwrite (patients + sessions) |
| AI Report | OpenRouter (via local Next.js API route) |

---

## 🏗️ System Architecture

```
┌──────────────────┐    Serial (USB)    ┌──────────────────┐    Socket.IO    ┌──────────────────┐
│  Arduino Mega    │ ─────────────────▶ │  Raspberry Pi 4  │ ────────────▶   │  Next.js Web     │
│  360 Hz Sampling │                    │  CNN Inference   │                 │  Dashboard       │
│  Multi-sensor    │                    │  FastAPI Server  │   REST API      │  Live Waveforms  │
└──────────────────┘                    └──────────────────┘                 └──────────────────┘
         ▲                                       ▲                                    │
   Biosensors                           AI Model (.keras)                    Browser / Tablet
 (ECG, SpO₂, IMU,                   Arrhythmia Classification             Real-time Patient View
  CO₂, Airflow)                        + CPET Parameters                         │
                                                                                   ▼
                                                                          ┌──────────────────┐
                                                                          │    Appwrite DB   │
                                                                          │  patients        │
                                                                          │  sessions        │
                                                                          └──────────────────┘
```

**Data Flow:**
- `Arduino → Pi`: USB Serial at 360 Hz
- `Pi → Browser`: Socket.IO real-time stream (live ECG, vitals, predictions)
- `Browser ↔ Pi`: REST API polling for session analytics (`/analysis/[id]`)
- `Browser ↔ Appwrite`: Patient record reads (client-side)
- `Pi → Appwrite`: Completed test session writes (backend-owned)
- `Browser → OpenRouter`: AI clinical report generation (via local Next API route)

---

## 🔌 Hardware Stack Status

| Component | Role | Status |
|-----------|------|--------|
| **AD8232** | ECG / HRV waveform (A0, D10/D11) | ✅ Planned & documented |
| **MAX30102** | SpO₂ + Pulse Rate (I²C pins 20/21) | ✅ Planned & documented |
| **MPU-6050** | Motion / Respiratory Rate (I²C) | ✅ Frontend support complete; backend parsing pending |
| **MQ-135 × 2** | Ambient CO₂ vs. Exhaled CO₂ (A1, A2) | ✅ Planned & documented |
| **Thermistor** | Hot-wire airflow / respiratory rate (A3) | ✅ Planned & documented |

> **Note:** Hardware integration is **not yet physically assembled and tested end-to-end.** The system operates in software simulation / degraded mode currently.

---

## ⚙️ Backend Status

**Location:** `backend/`  
**Entry Point:** `backend/main.py`  
**Framework:** FastAPI + Uvicorn  
**Storage:** In-memory (no persistent DB in current backend; Appwrite is used for patient/session persistence via Pi)

### REST API Endpoints

| Method | Endpoint | Status |
|--------|----------|--------|
| GET | `/` | ✅ Done |
| GET | `/api/status` | ✅ Done |
| POST | `/api/devices/heartbeat` | ✅ Done |
| GET | `/api/devices/status` | ✅ Done |
| POST | `/api/sessions/start` | ✅ Done |
| POST | `/api/sessions/{id}/stop` | ✅ Done |
| GET | `/api/sessions` | ✅ Done |
| GET | `/api/sessions/{id}` | ✅ Done |
| POST | `/api/events` | ✅ Done |
| GET | `/api/sessions/{id}/events` | ✅ Done |
| GET | `/api/sessions/{id}/stats` | ✅ Done |

### Socket.IO Events (Pi Server)

**Pi emits to frontend:**
- `server_status`, `sensor_status`, `processed_slow_1hz`, `cpet_parameters`
- `heart_rate`, `ecg_raw`, `cpet_stream`, `ecg_heart_rate`, `respiratory_rate`
- `prediction`, `statistics`
- `test_started`, `test_stopped`, `test_status`, `test_progress`
- `test_live_ecg`, `test_complete`, `test_result`, `all_test_results`
- `patient_id_set`, `error`

**Frontend emits to Pi:**
- `request_stats`, `request_sensor_status`
- `set_ecg_connection`, `set_ecg_mode`
- `start_test`, `stop_test`
- `get_test_status`, `get_test_status_request` (alias)
- `get_test_result`, `get_all_results`
- `set_patient_id`

### Backend Notable Milestones

- ✅ FastAPI server with 10+ REST endpoints
- ✅ In-memory session and event storage
- ✅ CORS configured (wildcard — needs production restriction)
- ✅ Appwrite `cpet_db` created with `patients` and `sessions` collections
- ✅ Schema verification passed (`patients missing []`, `sessions missing []`)
- ✅ Backend owns Appwrite writes for completed two-minute test sessions
- ✅ `get_test_status` Socket.IO alias added
- ✅ Patient identity (`patient_id` + `patient_name`) propagated into `test_complete`
- ✅ Degraded / no-Arduino startup mode supported
- ✅ Appwrite patient/session save smoke test passed

### Backend Limitations / TODOs

- ⚠️ **In-memory storage only** — data is lost on server restart; no persistent REST session DB
- ⚠️ CNN model validation described as **"weak"** — avoid diagnostic certainty in UI
- ⚠️ CORS wildcard (`allow_origins=["*"]`) — must be restricted before production deployment
- ⚠️ Pi backend still requires Arduino during initial startup (degraded mode partially addressed)

---

## 💻 Frontend / Dashboard Status

**Location:** `web_dashboard/`  
**Framework:** Next.js 16 (App Router) · TypeScript  
**State:** Validated clean — TypeScript pass, ESLint pass (0 errors, 0 warnings)

### Pages

| Route | Description | Status |
|-------|-------------|--------|
| `/` | Redirects to `/dashboard` | ✅ Done |
| `/dashboard` | Live ECG, vitals, test controls, patient ID entry | ✅ Done |
| `/ecg-monitor` | Full live ECG waveform + CNN predictions + vitals | ✅ Done |
| `/analysis` | Live analytics with class distribution charts + CPET strip | ✅ Done |
| `/analysis/[id]` | REST-backed session detail page (1s polling) | ✅ Done |
| `/patients` | Appwrite-backed patient list (search + Add Patient UI) | ✅ Done (partial CRUD) |
| `/report` | AI report generation via OpenRouter | ✅ Done |

### Key Components

| Component | Purpose | Status |
|-----------|---------|--------|
| `EcgChart.tsx` | Live ECG waveform renderer | ✅ Done |
| `PredictionDisplay.tsx` | CNN arrhythmia class + confidence display | ✅ Done |
| `VitalsPanel.tsx` | SpO₂, HR, Resp, MPU motion display | ✅ Done |
| `CPETParametersDisplay.tsx` | LRC, O₂ Pulse, LF/HF, PTT, VE/VCO₂ | ✅ Done |
| `AlertBanner.tsx` | Real-time arrhythmia alerts | ✅ Done |
| `ConnectionStatus.tsx` | Pi + Arduino status indicators | ✅ Done |
| `ECGModeControl.tsx` | ECG mode selector | ✅ Done |
| `app-layout.tsx` / `sidebar.tsx` / `header.tsx` | App shell | ✅ Done |

### Socket Protocol — `useECGSocket.ts`

- ✅ Confidence normalization (supports 0–1 and 0–100)
- ✅ `class_counts` (numeric key) and `class_distribution` (name key) mapping
- ✅ Test event flow: `test_progress`, `test_status`, `test_complete`, `test_result`
- ✅ `get_test_status` and `get_test_status_request` dual support
- ✅ Patient identity: `setPatientIdentity(patientId, patientName)` + alias `setPatientId`
- ✅ `patient_id_set` listener — stores accepted patient ID and name
- ✅ `sensor_status` Arduino degraded fields: `arduino_connected`, `arduino_stream_stale`, `arduino_last_data_age_sec`
- ✅ MPU6050 normalization from 7 different payload paths
- ✅ `prediction_active` and `prediction_status` — hides stale CNN predictions when hardware is down

### MPU6050 Respiratory Motion (Frontend)

- ✅ `MPU6050Data` TypeScript type shape defined
- ✅ Normalization from `processed_slow_1hz.respiratory_motion`, `sensor_status.mpu6050`, `cpet_parameters.respiratory_motion`, and top-level aliases (`ACC_X`, `GYRO_Z`, etc.)
- ✅ Live display: `Resp (MPU)` and `Motion` on `/dashboard` and `/ecg-monitor`
- ✅ Performance strip on `/analysis` includes respiratory-motion and artifact context
- ✅ AI report prompt includes MPU respiratory and motion data

### Derived CPET Metrics (Frontend)

| Metric | Field | Status |
|--------|-------|--------|
| LRC Ratio | `lrc_ratio` / `lrc_index` | ✅ Displayed |
| O₂ Pulse Surrogate | `o2_pulse_surrogate` | ✅ Displayed |
| CO₂ Delta | `co2_delta` / `net_co2` | ✅ Displayed |
| VE/VCO₂ Slope | `ve_vco2_slope_surrogate` | ✅ Displayed |
| PTT (ms) | `ptt_available` + value | ✅ Disabled when unavailable |
| Respiratory Rate | `respiratory_rate_bpm` + `respiratory_rate_source` | ✅ Displayed |
| Ventilatory Status | `ventilatory_efficiency_status` | ✅ Displayed |

### Frontend Validation Results (Last Run: 2026-04-22)

```
npx tsc --noEmit   →  ✅ PASS
npm run lint       →  ✅ PASS (0 errors, 0 warnings)
Dev server         →  ✅ HTTP 200 at localhost:3000
```

---

## 🤖 AI Model Status

**Location:** `backend/arrhythmia_cnn_final.keras`  
**Architecture:** 1D Convolutional Neural Network (CNN)  
**Dataset:** MIT-BIH Arrhythmia Database (110,000+ labelled beats)  
**Training notebook:** `backend/Arrythmia with MIT-BIH.ipynb`

| Property | Detail |
|----------|--------|
| **Classes** | 5 (Normal, Supraventricular, Ventricular, Fusion, Unknown/Paced) |
| **AAMI Mapping** | Class 0–4 |
| **Inference Rate** | ~360 Hz (real-time beat classification) |
| **Framework** | TensorFlow / Keras |
| **Model File** | `arrhythmia_cnn_final.keras` (557 KB) |
| **Backup Model** | `best_arrhythmia_model.keras` (557 KB) |
| **Validation** | Backend team cautions: validation is weak — UI copy softened to "screening/assistive" language |

**Status:** ✅ Trained · ✅ Saved · ✅ Loaded by backend · ⚠️ Validation thoroughness needs improvement

---

## 🔗 Integration Status

| Integration Point | Status | Notes |
|------------------|--------|-------|
| Arduino → Pi (Serial) | ⚠️ Pending HW test | Protocol documented; no physical end-to-end test yet |
| Pi CNN inference | ✅ Implemented | Keras model loaded; real-time beat classification |
| Pi → Frontend (Socket.IO) | ✅ Protocol aligned | All events normalized and handled on frontend |
| Frontend → Appwrite (reads) | ✅ Implemented | Patient records via client-side Appwrite SDK |
| Pi → Appwrite (writes) | ✅ Implemented | Completed sessions saved after test_complete |
| Frontend → OpenRouter (reports) | ✅ Implemented | Via local Next.js API route |
| MPU6050 data stream | ⚠️ Frontend ready | Backend MPU parsing / filtering pending full Arduino SLOW packet integration |
| PTT (Pulse Transit Time) | ⚠️ Disabled | Requires PPG waveform timing; currently shown as unavailable |

---

## ✅ Feature Completion Matrix

| Feature | Backend | Frontend | Tested |
|---------|---------|----------|--------|
| Live ECG waveform display | ✅ | ✅ | ⚠️ Simulation only |
| Real-time arrhythmia classification | ✅ | ✅ | ⚠️ Simulation only |
| CNN confidence display | ✅ | ✅ | ⚠️ Simulation only |
| SpO₂ / HR vitals display | ✅ | ✅ | ⚠️ Simulation only |
| CPET parameter display | ✅ | ✅ | ⚠️ Simulation only |
| Two-minute structured test | ✅ | ✅ | ⚠️ Not Pi-tested |
| Patient identity handoff | ✅ | ✅ | ⚠️ Not Pi-tested |
| Patient required validation | ✅ | ✅ | ⚠️ Not Pi-tested |
| Appwrite session persistence | ✅ | N/A | ✅ Smoke tested |
| Appwrite patient reads | N/A | ✅ | ⚠️ Not fully verified |
| AI report generation | N/A | ✅ | ⚠️ Requires API key |
| MPU6050 respiratory motion | ⚠️ Partial | ✅ | ⚠️ Not Pi-tested |
| Arduino degraded mode | ✅ | ✅ | ⚠️ Not Pi-tested |
| Session analysis page | ✅ | ✅ | ⚠️ Simulation only |
| Patient management CRUD | ❌ Not started | ⚠️ UI only | ❌ |
| PTT (cuffless BP) | ❌ Requires PPG | ⚠️ Shows disabled | ❌ |
| Physical hardware assembly | ❌ Not done | N/A | ❌ |

---

## 🚧 Known Issues & Blockers

### Critical
- ❌ **No physical hardware test** — Full end-to-end test (Arduino → Pi → Browser) has not been conducted.
- ❌ **PTT unavailable** — Pulse Transit Time requires synchronised PPG waveform ECG-to-PPG delay measurement; MAX30102 not yet integrated at signal-processing level.
- ❌ **CNN validation weak** — Model was trained on MIT-BIH but has not been independently validated on a held-out clinical dataset. Cannot be used for diagnostic claims.

### High Priority
- ⚠️ **In-memory backend storage** — Sessions and events are lost on backend restart. No SQLite/PostgreSQL persistence layer in the REST backend.
- ⚠️ **CORS wildcard** — `allow_origins=["*"]` in `backend/main.py` must be restricted before any networked deployment.
- ⚠️ **Appwrite API key in `setup-appwrite.js`** — If the key is real, it must be rotated and moved to environment variables immediately.
- ⚠️ **Patient CRUD incomplete** — The `/patients` page has Search and Add Patient UI but these are not wired to a full create/update/delete flow.

### Medium Priority
- ⚠️ **MPU6050 backend parsing incomplete** — Frontend is ready to display MPU respiratory motion data, but backend MPU filtering, rate estimation, and SLOW packet integration still need work.
- ⚠️ **Pi server URL env** — Falls back to hardcoded `http://mypi.local:5000` when `NEXT_PUBLIC_PI_SERVER_URL` is missing. This must be set correctly in `.env.local`.
- ⚠️ **Report requires `OPENROUTER_API_KEY`** — Without this key, AI clinical report generation falls back to demo mode.

---

## 📌 Pending Work & Next Steps

### Immediate (High Priority)
1. **Physical Hardware Assembly** — Solder and connect AD8232, MAX30102, MPU-6050, MQ-135 × 2, and Thermistor to Arduino Mega per the pin map in `README.md`.
2. **Arduino Firmware** — Upload 360 Hz ECG sampling sketch; verify serial output format matches Pi parser expectations.
3. **Pi Integration Test** — Connect Arduino to Pi via USB, start Pi Socket.IO server, verify live data reaches the Next.js dashboard.
4. **Rotate Appwrite API key** in `setup-appwrite.js` if it is a real credential.

### Short Term
5. **Restrict CORS** in `backend/main.py` to Pi and dashboard origins only.
6. **Backend DB persistence** — Replace in-memory `sessions_db` / `events_db` with SQLite or a proper DB so sessions survive restarts.
7. **MPU6050 backend integration** — Complete backend parsing and filtering of Arduino SLOW packets (`ACC_X`, `GYRO_X`, etc.) and emit `processed_slow_1hz.respiratory_motion`.
8. **Verify Pi-connected/Arduino-unavailable UI** — Test that frontend correctly shows Pi connected + Arduino offline in degraded mode.

### Medium Term
9. **Patient CRUD flow** — Wire Add Patient and Edit Patient forms to Appwrite database.
10. **CNN model validation** — Evaluate model on a separate held-out dataset and document accuracy, sensitivity, and specificity per AAMI class.
11. **PTT implementation** — Synchronise ECG R-peak detection with MAX30102 PPG peak detection to compute cuffless PTT/BP estimates.
12. **Production hardening** — Restrict CORS, remove API key fallbacks, add rate limiting, implement HTTPS for Pi server.

### Research & Documentation
13. **Model performance report** — Document confusion matrix, per-class accuracy, and clinical false-positive/negative rates.
14. **System latency benchmarks** — Measure Arduino → Pi → Browser end-to-end latency under live conditions.
15. **Clinical validation plan** — Design a protocol for comparing CPET system output against a reference clinical CPET system.

---

## 🔐 Security Checklist

| Item | Status |
|------|--------|
| Backend Appwrite API keys not in frontend bundle | ✅ Enforced |
| `OPENROUTER_API_KEY` server-side only (Next API route) | ✅ Done |
| `setup-appwrite.js` hardcoded key | ⚠️ **NEEDS ROTATION** |
| CORS wildcard in `backend/main.py` | ⚠️ Must restrict before deployment |
| `.env.local` excluded from git | ✅ (in `.gitignore`) |
| No secret values in Python source files | ✅ Backend confirmed |

---

## 🗂️ Environment & Configuration

### Required Environment Variables

```bash
# web_dashboard/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000           # FastAPI backend
NEXT_PUBLIC_PI_SERVER_URL=http://mypi.local:5000   # Pi Socket.IO server
NEXT_PUBLIC_APPWRITE_ENDPOINT=...
NEXT_PUBLIC_APPWRITE_PROJECT_ID=...
NEXT_PUBLIC_APPWRITE_DATABASE_ID=...
NEXT_PUBLIC_APPWRITE_PATIENTS_COLLECTION_ID=...
OPENROUTER_API_KEY=...                              # Server-side only
```

### How to Run Locally

```powershell
# Terminal 1 — Backend
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2 — Frontend
cd web_dashboard
npm install
npm run dev
# → http://localhost:3000
```

Or use the provided batch launchers:
- `start_backend.bat`
- `start_frontend.bat`
- `start_cpet_system.bat` (launches both)

---

## 📁 Project File Map

```
CPET_system/
├── backend/
│   ├── main.py                          ✅ FastAPI server (10 endpoints)
│   ├── requirements.txt                 ✅ Python deps
│   ├── arrhythmia_cnn_final.keras       ✅ Trained CNN model (557 KB)
│   ├── best_arrhythmia_model.keras      ✅ Backup model
│   ├── test_api.py                      ✅ API test script
│   └── Arrythmia with MIT-BIH.ipynb    ✅ Training notebook
│
├── web_dashboard/
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx                 ✅ Redirect to /dashboard
│   │   │   ├── dashboard/page.tsx       ✅ Main monitoring page
│   │   │   ├── ecg-monitor/page.tsx     ✅ Full ECG + vitals
│   │   │   ├── analysis/page.tsx        ✅ Live analytics
│   │   │   ├── analysis/[id]/page.tsx   ✅ Session detail (REST)
│   │   │   ├── patients/page.tsx        ✅ Patient list (Appwrite)
│   │   │   ├── report/page.tsx          ✅ AI report page
│   │   │   └── api/generate-report/     ✅ OpenRouter route
│   │   ├── components/
│   │   │   ├── ecg/                     ✅ 8 specialized components
│   │   │   ├── layout/                  ✅ AppLayout, Sidebar, Header
│   │   │   └── ui/                      ✅ Button, Card, Input, Table
│   │   ├── lib/
│   │   │   ├── api.ts                   ✅ REST client
│   │   │   ├── useECGSocket.ts          ✅ Socket.IO hook (fully normalized)
│   │   │   ├── ecg-config.ts            ✅ Event names + server config
│   │   │   ├── appwrite.ts              ✅ Appwrite client config
│   │   │   └── utils.ts                 ✅ Utilities
│   │   └── types/index.ts               ✅ Full TypeScript type definitions
│   └── .env.local                       ✅ Local env (not in git)
│
├── README.md                            ✅ Main project documentation
├── PROGRESS_REPORT.md                   ← This file
├── CURRENT_STATE_FRONTEND.md           ✅ Frontend audit (2026-04-22)
├── FRONTEND_TEAM_BACKEND_REPORT.md     ✅ Integration handoff (2026-04-22)
├── INTEGRATION_README.md               ✅ Hardware integration guide
├── QUICK_START.md                       ✅ 5-minute setup guide
├── CPET_PARAMETERS_GUIDE.md            ✅ Clinical parameter reference
├── set_cache_envs.ps1                   ✅ Windows cache config
├── start_backend.bat                    ✅ Backend launcher
├── start_frontend.bat                   ✅ Frontend launcher (repaired)
└── start_cpet_system.bat               ✅ Full system launcher
```

---

## 📊 Overall Progress Summary

| Domain | Progress |
|--------|----------|
| Hardware Planning | ████████░░ 80% |
| Physical Hardware Assembly | ██░░░░░░░░ 15% |
| Backend (FastAPI REST) | ████████░░ 80% |
| Pi Socket.IO Server | ██████░░░░ 65% |
| CNN Model (Training) | █████████░ 90% |
| CNN Model (Validation) | ████░░░░░░ 40% |
| Frontend Dashboard | █████████░ 90% |
| Frontend-Backend Integration | ███████░░░ 70% |
| End-to-End Hardware Test | ██░░░░░░░░ 15% |
| Appwrite Database | ████████░░ 80% |
| Security Hardening | █████░░░░░ 50% |
| Documentation | ████████░░ 85% |

**Overall Estimated Completion: ~68%**

---

*Report compiled from: `README.md`, `CURRENT_STATE_FRONTEND.md`, `FRONTEND_TEAM_BACKEND_REPORT.md`, `INTEGRATION_README.md`, `QUICK_START.md`, `backend/main.py`, and project file structure analysis.*

*Last updated: 2026-07-03*

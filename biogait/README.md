# SmartCPET-RehabGuard BioGait

Real-time RGB camera-based movement analysis prototype using MediaPipe pose estimation.

> **Screening / decision-support architecture — not a clinical diagnostic device.**
> The current risk scoring is a legacy rule-based experimental screening baseline and is not clinically validated.

## Runtime Architecture

### Primary Runtime (Qt Desktop)

```
app_qt.py
    ↓
ui_worker.py  (QThread: camera + MediaPipe Tasks PoseLandmarker)
    ↓
metrics.py    (biomechanical calculations + risk scoring)
    ↓
PyQt5 dashboard (VideoPanel + DashboardPanel + Sparklines)
```

This is the conference-primary entry point:

```powershell
python app_qt.py
```

### Legacy Runtime (OpenCV Window + File Logging)

`app.py` is the legacy OpenCV implementation. It writes metrics to `latest_metrics.json` and `outputs/session_metrics.csv`.

`dashboard.py` is a Streamlit companion that **reads `latest_metrics.json` produced by `app.py`**. It is NOT currently fed by `app_qt.py`. These two runtimes are not synchronized.

```powershell
# Legacy only:
python app.py

# In a separate terminal, for the legacy Streamlit view:
streamlit run dashboard.py
```

## Files

| File | Role |
|------|------|
| `app_qt.py` | **Primary** — PyQt5 desktop application |
| `ui_worker.py` | Camera + MediaPipe worker (QThread) |
| `ui_widgets.py` | PyQt5 reusable UI widgets |
| `app.py` | **Legacy** — OpenCV window + file logging |
| `dashboard.py` | **Legacy** — Streamlit dashboard (reads app.py output) |
| `metrics.py` | Biomechanical angle/risk calculations |
| `pose_utils.py` | Landmark extraction + OpenCV drawing |
| `config.py` | Camera source, thresholds, output paths |
| `requirements.txt` | Python dependencies |
| `pose_landmarker_lite.task` | MediaPipe PoseLandmarker model (pretrained) |

## Setup

Python 3.10 or 3.11 is recommended:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Camera Configuration

Default: laptop webcam (index 0).

To use a phone IP camera, set the environment variable:

```powershell
# PowerShell
$env:BIOGAIT_CAMERA_SOURCE="http://PHONE_IP:8080/video"
python app_qt.py
```

```bash
# Bash / Linux
export BIOGAIT_CAMERA_SOURCE="http://PHONE_IP:8080/video"
python app_qt.py
```

See `.env.example` for available configuration variables.

## Metrics

The prototype calculates:

- Left / right knee angle (2D, degrees from landmark triplet)
- Trunk lean angle (degrees from image vertical)
- Knee angle asymmetry (absolute left-right difference)
- Hip height imbalance (2D normalized surrogate)
- Ankle alignment difference (2D normalized surrogate)
- Risk score 0–100 (legacy rule-based heuristic)
- Risk level: LOW / MODERATE / HIGH

These are **legacy rule-based experimental screening baselines**. They are not clinically validated and should not be used for medical decisions.

## Demo Placement

- Side view: camera distance 2–3 m, waist to chest height, full body visible, good lighting
- Side view is best for knee angle and trunk lean
- Front view is better for left-right posture and alignment demonstrations

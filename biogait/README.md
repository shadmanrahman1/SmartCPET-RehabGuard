# SmartCPET-RehabGuard BioGait Camera Prototype

This is a camera-only MediaPipe demo for the BioGait module. It uses a laptop webcam or mobile IP camera stream, detects body landmarks, calculates simple biomechanical indicators, and writes live metrics for a Streamlit dashboard.

The output is a screening score only. It is not a clinical diagnosis.

## Files

- `app.py` - OpenCV and MediaPipe live camera loop
- `metrics.py` - angle, asymmetry, and risk-score calculations
- `pose_utils.py` - landmark extraction and video overlay helpers
- `config.py` - camera source, thresholds, and output paths
- `dashboard.py` - Streamlit dashboard reading `latest_metrics.json`
- `outputs/session_metrics.csv` - session metrics log
- `outputs/screenshots/` - screenshots saved from the camera app

## Setup on Windows

From this folder, Python 3.10 is recommended for the smoothest MediaPipe install:

```powershell
py -3.10 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks venv activation, open Command Prompt and run:

```cmd
venv\Scripts\activate.bat
```

If the `py -3.10` launcher is not available, install Python 3.10 or 3.11 and create the venv with that version.

## Run with the laptop webcam

In `config.py`, keep:

```python
CAMERA_SOURCE = 0
```

Then run:

```powershell
python app.py
```

Keyboard controls:

- `q` - quit
- `s` - save screenshot
- `r` - reset session CSV

## Run with a mobile IP camera

Connect the phone and laptop to the same Wi-Fi. Start an Android IP camera app such as IP Webcam, DroidCam, Iriun, Camo, or OBS DroidCam.

For IP Webcam, the stream is usually:

```text
http://PHONE_IP:8080/video
```

Set it in `config.py`:

```python
CAMERA_SOURCE = "http://192.168.0.105:8080/video"
```

Or use a temporary PowerShell override:

```powershell
$env:BIOGAIT_CAMERA_SOURCE="http://192.168.0.105:8080/video"
python app.py
```

## Run the dashboard

Keep `app.py` running in one terminal. Open another terminal:

```powershell
streamlit run dashboard.py
```

Open:

```text
http://localhost:8501
```

To open the dashboard from a phone on the same Wi-Fi:

```powershell
streamlit run dashboard.py --server.address 0.0.0.0
```

Then browse from the phone to:

```text
http://LAPTOP_IP:8501
```

Find `LAPTOP_IP` with:

```powershell
ipconfig
```

## Demo placement

Start with a side view:

- Camera distance: 2 to 3 meters
- Camera height: waist to chest level
- Full body visible
- Good lighting

Side view is best for knee angle and trunk lean. Front view is better for left-right posture and alignment demonstrations.

## Metrics

The prototype calculates:

- left knee angle
- right knee angle
- trunk lean angle
- knee angle asymmetry
- hip height imbalance as a 2D camera-visible surrogate
- ankle alignment difference as a 2D camera-visible surrogate
- risk score from 0 to 100
- risk level: LOW, MODERATE, or HIGH
- reason list

Rule-based score examples:

- high knee angle asymmetry increases risk
- high trunk lean increases risk
- visible hip imbalance increases risk
- visible ankle alignment difference increases risk
- low landmark confidence adds a warning

This is intended for a prototype demo and should be validated clinically before any real medical use.

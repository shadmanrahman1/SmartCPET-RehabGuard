# CPET Robust Parameters - Raspberry Pi Implementation Guide

This guide explains how to calculate and emit the 6 CPET parameters from your Raspberry Pi to the Next.js dashboard.

## Overview

The laptop dashboard is now ready to display these medical parameters. Your Raspberry Pi needs to:
1. Calculate parameters after each heartbeat detection
2. Emit them via Socket.IO event: `'cpet_parameters'`

---

## Data Structure to Emit

```python
cpet_data = {
    "lrc_ratio": 0.25,              # Breathing Rate / Heart Rate
    "oxygen_pulse": 12.5,           # VO2/HR in ml/beat
    "lf_hf_ratio": 1.2,             # Low Freq / High Freq power (HRV)
    "ptt_ms": 280.0,                # Pulse Transit Time in milliseconds
    "ve_vco2_slope": 28.5,          # Ventilatory Efficiency slope
    "heart_rate_bpm": 75.0,         # Current HR from R-R intervals
    "timestamp": int(time.time() * 1000),
    "data_quality": "good"          # 'excellent', 'good', 'fair', 'poor'
}

# Emit to dashboard
socketio.emit('cpet_parameters', cpet_data)
```

---

## Calculation Methods

### 1. LRC Ratio (Lung-Respiratory-Cardiac Ratio)

```python
from collections import deque
import time

# Global buffers
rr_intervals = deque(maxlen=10)  # Last 10 R-R intervals
breath_times = deque(maxlen=10)  # Last 10 breath cycle times

def calculate_lrc_ratio():
    """
    LRC Ratio = Breathing Rate / Heart Rate
    Normal range: 0.20 - 0.30
    """
    if len(rr_intervals) < 3 or len(breath_times) < 3:
        return None
    
    # Calculate Heart Rate from R-R intervals
    avg_rr_interval_sec = sum(rr_intervals) / len(rr_intervals)
    heart_rate_bpm = 60.0 / avg_rr_interval_sec if avg_rr_interval_sec > 0 else None
    
    # Calculate Breathing Rate from breath cycle times
    avg_breath_interval_sec = sum(breath_times) / len(breath_times)
    breathing_rate_bpm = 60.0 / avg_breath_interval_sec if avg_breath_interval_sec > 0 else None
    
    if heart_rate_bpm and breathing_rate_bpm:
        lrc_ratio = breathing_rate_bpm / heart_rate_bpm
        return round(lrc_ratio, 3)
    
    return None

# After detecting R-peak:
current_time = time.time()
if last_r_peak_time is not None:
    rr_interval = current_time - last_r_peak_time
    rr_intervals.append(rr_interval)
last_r_peak_time = current_time
```

### 2. Oxygen Pulse (VO₂/HR)

```python
# Requires external VO2 sensor or estimation
vo2_ml_per_min = 1500.0  # From gas analyzer or estimated

def calculate_oxygen_pulse(vo2_ml_per_min, heart_rate_bpm):
    """
    Oxygen Pulse = VO2 / Heart Rate
    Normal range: 10-20 ml/beat
    """
    if heart_rate_bpm and heart_rate_bpm > 0:
        oxygen_pulse = vo2_ml_per_min / heart_rate_bpm
        return round(oxygen_pulse, 2)
    return None
```

### 3. LF/HF Ratio (Heart Rate Variability)

```python
import numpy as np
from scipy import signal

# Requires at least 60 seconds of R-R intervals
rr_buffer = deque(maxlen=360)  # ~60s at 360Hz sampling

def calculate_lf_hf_ratio(rr_intervals_ms):
    """
    Frequency domain HRV analysis
    LF: 0.04-0.15 Hz, HF: 0.15-0.4 Hz
    """
    if len(rr_intervals_ms) < 60:
        return None
    
    # Resample to uniform time series (4Hz is standard)
    rr_array = np.array(rr_intervals_ms)
    
    # Welch's method for power spectral density
    fs = 4.0  # Sampling frequency after interpolation
    f, psd = signal.welch(rr_array, fs=fs, nperseg=256)
    
    # Define frequency bands
    lf_band = (f >= 0.04) & (f <= 0.15)
    hf_band = (f >= 0.15) & (f <= 0.4)
    
    # Calculate power in each band
    lf_power = np.trapz(psd[lf_band], f[lf_band])
    hf_power = np.trapz(psd[hf_band], f[hf_band])
    
    if hf_power > 0:
        lf_hf = lf_power / hf_power
        return round(lf_hf, 2)
    
    return None
```

### 4. PTT - Pulse Transit Time

```python
# Requires synchronized ECG and PPG sensors
last_ecg_r_peak_time = None
last_ppg_peak_time = None

def calculate_ptt():
    """
    PTT = Time from ECG R-peak to PPG systolic peak
    Typical range: 200-350 ms
    Used for cuffless blood pressure estimation
    """
    if last_ecg_r_peak_time and last_ppg_peak_time:
        if last_ppg_peak_time > last_ecg_r_peak_time:
            ptt_ms = (last_ppg_peak_time - last_ecg_r_peak_time) * 1000
            return round(ptt_ms, 1)
    return None

# In your main loop:
# After ECG R-peak detected:
last_ecg_r_peak_time = time.time()

# After PPG peak detected (using MAX30100):
last_ppg_peak_time = time.time()
```

### 5. VE/VCO₂ Slope (Ventilatory Efficiency)

```python
from scipy.stats import linregress

# Buffers for regression
ve_values = []  # Minute Ventilation (L/min)
vco2_values = []  # CO2 production (L/min)

def calculate_ve_vco2_slope():
    """
    Slope of VE vs VCO2 regression line
    Normal range: 20-30
    Higher values (>35) indicate cardiopulmonary issues
    """
    if len(ve_values) < 10 or len(vco2_values) < 10:
        return None
    
    # Linear regression
    slope, intercept, r_value, p_value, std_err = linregress(vco2_values, ve_values)
    
    return round(slope, 2)

# Update buffers continuously:
# (Requires flow sensor and CO2 analyzer)
ve_values.append(current_ve)
vco2_values.append(current_vco2)
```

### 6. Heart Rate (from R-R intervals)

```python
def calculate_heart_rate(rr_intervals):
    """
    Real-time heart rate from R-R intervals
    """
    if len(rr_intervals) < 3:
        return None
    
    avg_rr_sec = sum(rr_intervals) / len(rr_intervals)
    hr_bpm = 60.0 / avg_rr_sec if avg_rr_sec > 0 else None
    
    return round(hr_bpm, 1) if hr_bpm else None
```

---

## Integration into Raspberry Pi main.py

```python
from flask import Flask
from flask_socketio import SocketIO
from collections import deque
import time

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Global buffers
rr_intervals = deque(maxlen=10)
last_r_peak_time = None

def emit_cpet_parameters():
    """
    Calculate and emit all CPET parameters
    Call this after each heartbeat detection
    """
    # Calculate each parameter
    lrc = calculate_lrc_ratio()
    oxygen_pulse = calculate_oxygen_pulse(1500, calculate_heart_rate(rr_intervals))
    lf_hf = calculate_lf_hf_ratio(list(rr_intervals))
    ptt = calculate_ptt()
    ve_vco2 = calculate_ve_vco2_slope()
    hr = calculate_heart_rate(rr_intervals)
    
    # Determine data quality based on signal stability
    data_quality = "good"
    if len(rr_intervals) < 5:
        data_quality = "poor"
    elif lrc and 0.15 < lrc < 0.35:
        data_quality = "excellent"
    
    cpet_data = {
        "lrc_ratio": lrc,
        "oxygen_pulse": oxygen_pulse,
        "lf_hf_ratio": lf_hf,
        "ptt_ms": ptt,
        "ve_vco2_slope": ve_vco2,
        "heart_rate_bpm": hr,
        "timestamp": int(time.time() * 1000),
        "data_quality": data_quality
    }
    
    # Emit to dashboard
    socketio.emit('cpet_parameters', cpet_data)
    print(f"[CPET] HR: {hr} bpm, LRC: {lrc}, O2 Pulse: {oxygen_pulse}")

# In your Pan-Tompkins R-peak detection loop:
def on_r_peak_detected(peak_time):
    global last_r_peak_time
    
    if last_r_peak_time is not None:
        rr_interval = peak_time - last_r_peak_time
        rr_intervals.append(rr_interval)
        
        # Emit updated parameters every heartbeat
        emit_cpet_parameters()
    
    last_r_peak_time = peak_time
```

---

## Testing Without Sensors

If you don't have all sensors yet, emit mock data:

```python
import random

def emit_mock_cpet_parameters():
    """
    For testing the dashboard without full sensor setup
    """
    cpet_data = {
        "lrc_ratio": round(random.uniform(0.20, 0.30), 3),
        "oxygen_pulse": round(random.uniform(10, 18), 2),
        "lf_hf_ratio": round(random.uniform(0.8, 2.5), 2),
        "ptt_ms": round(random.uniform(220, 320), 1),
        "ve_vco2_slope": round(random.uniform(22, 32), 2),
        "heart_rate_bpm": round(random.uniform(60, 100), 1),
        "timestamp": int(time.time() * 1000),
        "data_quality": random.choice(["excellent", "good", "fair"])
    }
    
    socketio.emit('cpet_parameters', cpet_data)

# Call every 2 seconds for testing:
socketio.start_background_task(
    lambda: [emit_mock_cpet_parameters() or time.sleep(2) for _ in iter(int, 1)]
)
```

---

## Dashboard Display

The Next.js dashboard will automatically:
- ✅ Display all 6 parameters in color-coded cards
- ✅ Show warning colors when values are out of normal range
- ✅ Provide clinical interpretation hints
- ✅ Update in real-time as data arrives

Just emit the `'cpet_parameters'` event from your Pi and the dashboard handles the rest!

---

## Required Python Libraries

```bash
pip install scipy numpy flask flask-socketio
```

---

## Next Steps

1. **Choose Your Sensors**: Determine which parameters you can calculate with your current hardware
2. **Implement Calculations**: Add the calculation functions to your Pi code
3. **Test with Mock Data**: Use the mock function to verify dashboard display
4. **Integrate Real Sensors**: Replace mock data with actual calculations as sensors are added
5. **Optimize**: Adjust update frequency (currently every heartbeat) based on computational load

The dashboard is ready to receive these parameters whenever your Pi starts sending them!

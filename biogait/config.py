from pathlib import Path
import os


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"
SCREENSHOT_DIR = OUTPUT_DIR / "screenshots"

LATEST_METRICS_PATH = BASE_DIR / "latest_metrics.json"
SESSION_METRICS_PATH = OUTPUT_DIR / "session_metrics.csv"

# Use 0 for the laptop webcam.
# For an Android IP Webcam stream, set the URL here or use the environment variable.
# Example: CAMERA_SOURCE = "http://192.168.0.105:8080/video"
CAMERA_SOURCE = 0

# Override via environment variable without editing this file:
# PowerShell:  $env:BIOGAIT_CAMERA_SOURCE="http://192.168.0.105:8080/video"
# Bash/Linux:   export BIOGAIT_CAMERA_SOURCE="http://192.168.0.105:8080/video"
CAMERA_SOURCE_ENV = "BIOGAIT_CAMERA_SOURCE"

WINDOW_NAME = "SmartCPET-RehabGuard BioGait"
FRAME_WIDTH = 1280
FRAME_HEIGHT = 720
FRAME_FPS = 30
MIRROR_LAPTOP_WEBCAM = True

MIN_LANDMARK_VISIBILITY = 0.55
LOW_CONFIDENCE_AVG_VISIBILITY = 0.65

KNEE_ASYMMETRY_MODERATE_DEG = 12.0
KNEE_ASYMMETRY_HIGH_DEG = 20.0
TRUNK_LEAN_MODERATE_DEG = 10.0
TRUNK_LEAN_HIGH_DEG = 15.0

# These are simple camera-visible surrogate indicators from 2D landmarks.
HIP_IMBALANCE_WARNING = 0.04
ANKLE_ALIGNMENT_WARNING = 0.06

LATEST_WRITE_INTERVAL_SECONDS = 0.25
CSV_WRITE_INTERVAL_SECONDS = 1.0

POSE_MODEL_COMPLEXITY = 1
POSE_MIN_DETECTION_CONFIDENCE = 0.5
POSE_MIN_TRACKING_CONFIDENCE = 0.5


def get_camera_source():
    """Return the configured camera source, allowing a simple env override."""
    raw_source = os.getenv(CAMERA_SOURCE_ENV, CAMERA_SOURCE)
    if isinstance(raw_source, str) and raw_source.strip().isdigit():
        return int(raw_source.strip())
    return raw_source


def ensure_output_dirs():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

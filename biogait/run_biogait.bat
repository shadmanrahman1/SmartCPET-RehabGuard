@echo off
echo ===================================================
echo     SmartCPET-RehabGuard BioGait Launcher
echo ===================================================
echo.
echo Camera source is configured via BIOGAIT_CAMERA_SOURCE.
echo Default: webcam (index 0).
echo.
echo To use an IP camera, set the environment variable before launching:
echo   set BIOGAIT_CAMERA_SOURCE=http://PHONE_IP:8080/video
echo.

cd /d "%~dp0"

REM Activate local venv if it exists
if exist ".\venv\Scripts\activate.bat" (
    echo Using local venv...
    call .\venv\Scripts\activate.bat
) else (
    echo No local venv found. Using system Python.
)

echo Starting BioGait (Qt desktop)...
python app_qt.py

pause

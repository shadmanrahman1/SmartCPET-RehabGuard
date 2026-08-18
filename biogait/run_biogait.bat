@echo off
echo ===================================================
echo     SmartCPET-RehabGuard BioGait Launcher
echo ===================================================
echo.
echo Make sure your phone's IP Webcam app is running and 
echo connected to the same Wi-Fi network.
echo.
echo If the app shows "NO_SIGNAL" or "ERROR", check the IP
echo in config.py (currently set to 192.168.1.101:8080).
echo.
echo Starting application...
echo.

cd /d "%~dp0"
call .\venv\Scripts\activate.bat
python app_qt.py

pause

@echo off
title CPET System Launcher
color 0A

echo ========================================
echo   🫀 KUET BME CPET SYSTEM LAUNCHER 🫀
echo ========================================
echo.
echo 🎯 System Status Check:
echo   ✅ Pi Connection: http://mypi.local:5000
echo   ✅ Backend API:   http://localhost:8000  
echo   ✅ Frontend:      http://localhost:3000
echo.
echo 🚀 Starting servers...
echo.

echo [1/2] Starting Backend API Server...
start "CPET Backend API" cmd /k "%~dp0start_backend.bat"

echo [2/2] Starting Frontend Dashboard...
timeout /t 3 /nobreak >nul
start "CPET Frontend" cmd /k "%~dp0start_frontend.bat"

echo.
echo ✅ All servers started!
echo.
echo 📊 Open these URLs:
echo   • Dashboard: http://localhost:3000
echo   • API Docs:  http://localhost:8000/docs
echo.
echo 💡 Both servers are running in separate windows.
echo    Close those windows to stop the servers.
echo.
pause
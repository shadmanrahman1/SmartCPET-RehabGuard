@echo off
echo =====================================
echo  CPET System - Starting Backend API
echo =====================================

cd /d "%~dp0backend"

echo Checking Python environment...
python --version
if errorlevel 1 (
    echo ERROR: Python not found! Please install Python.
    pause
    exit /b 1
)

echo Installing/checking dependencies...
python -m pip install fastapi uvicorn pydantic python-multipart --quiet

echo Starting FastAPI server on http://localhost:8000...
echo Press Ctrl+C to stop the server
echo.

python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
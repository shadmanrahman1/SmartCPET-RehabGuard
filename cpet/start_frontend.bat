@echo off
echo =====================================
echo  CPET System - Starting Frontend
echo =====================================

cd /d "%~dp0web_dashboard"

echo Checking Node.js environment...
node --version
if errorlevel 1 (
    echo ERROR: Node.js not found! Please install Node.js.
    pause
    exit /b 1
)

echo Installing/checking dependencies...
call npm install

echo Starting Next.js development server...
echo Dashboard will be available at: http://localhost:3000
echo Press Ctrl+C to stop the server
echo.

call npm run dev

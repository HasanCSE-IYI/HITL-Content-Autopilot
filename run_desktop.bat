@echo off
title HITL Content Autopilot v2.0 - Amazon Affiliate Blog Studio
color 0B

echo =========================================================================
echo    🛒 AMAZON AFFILIATE BLOG AUTOPILOT - WINDOWS DESKTOP LAUNCHER
echo =========================================================================
echo.
echo [1/3] Verifying Python Environment...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not found in your system PATH.
    echo Please install Python 3.11+ from https://www.python.org/
    pause
    exit /b 1
)

echo [2/3] Checking dependencies...
python -c "import streamlit, requests, markdown" >nul 2>&1
if %errorlevel% neq 0 (
    echo [NOTICE] Installing missing dependencies from requirements.txt...
    pip install -r requirements.txt
)

echo [3/3] Launching Local Desktop Application on http://localhost:8501...
echo.
echo Opening HITL Content Autopilot in your default browser...
echo Press CTRL+C in this terminal window to stop the application.
echo.

python -m streamlit run app.py --server.port 8501 --server.headless false

pause

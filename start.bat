@echo off
TITLE ETAFlow - Smart Delivery Intelligence Platform
echo ===========================================================================
echo ETAFlow: MLOps & Delivery Intelligence Platform Launcher
echo ===========================================================================
echo.

cd /d "%~dp0"

set "PYTHONPATH=%~dp0src;%PYTHONPATH%"

IF EXIST "%~dp0.venv\Scripts\python.exe" (
    set "PY_BIN=%~dp0.venv\Scripts\python.exe"
) ELSE (
    set "PY_BIN=python"
)

IF NOT EXIST ".env" (
    IF EXIST ".env.example" (
        echo [INFO] Creating .env from .env.example...
        copy .env.example .env >nul
    )
)

echo [1/3] Starting ETAFlow Prediction API on http://127.0.0.1:8000 ...
start "ETAFlow API Service" /min cmd /c "cd /d "%~dp0" && set "PYTHONPATH=%~dp0src" && "%PY_BIN%" pipelines\serve_api.py"

echo [2/3] Waiting for API service to become ready...
timeout /t 3 /nobreak >nul

echo [3/3] Opening Web Dashboard on http://127.0.0.1:8501 ...
start "" "http://127.0.0.1:8501"

echo.
echo ===========================================================================
echo ETAFlow is actively running!
echo - API Server:  http://127.0.0.1:8000 (Health: http://127.0.0.1:8000/health)
echo - Dashboard:   http://127.0.0.1:8501
echo.
echo Leave this window open while using the platform. Press CTRL+C to stop.
echo ===========================================================================
echo.

"%PY_BIN%" -m http.server 8501 --directory app

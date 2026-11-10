@echo off
TITLE ETAFlow - Smart Delivery Intelligence Platform
echo ===========================================================================
echo ETAFlow: MLOps & Delivery Intelligence Platform Launcher
echo ===========================================================================
echo.

cd /d "%~dp0"

IF NOT EXIST ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment (.venv) not found.
    echo Please run: python -m venv .venv ^&^& .\.venv\Scripts\pip install -e ".[dev]" mlflow
    pause
    exit /b 1
)

IF NOT EXIST ".env" (
    IF EXIST ".env.example" (
        echo [INFO] Creating .env from .env.example...
        copy .env.example .env >nul
    )
)

echo [1/3] Starting ETAFlow Prediction API on http://127.0.0.1:8000 ...
set PYTHONPATH=src
start "ETAFlow API Service" /min cmd /c "set PYTHONPATH=src&& .\.venv\Scripts\python.exe pipelines\serve_api.py"

echo [2/3] Waiting for API service to become ready...
timeout /t 3 /nobreak >nul

echo [3/3] Launching Web Dashboard on http://127.0.0.1:8501 ...
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

.\.venv\Scripts\python.exe -m http.server 8501 --directory app


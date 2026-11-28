@echo off
TITLE ETAFlow - Smart Delivery Intelligence Platform
echo ===========================================================================
echo ETAFlow: MLOps ^& Delivery Intelligence Platform Launcher
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

echo [1/2] Opening ETAFlow in your browser in a few seconds: http://127.0.0.1:8000/
start "" /min cmd /c "timeout /t 3 /nobreak >nul && start "" "http://127.0.0.1:8000/""

echo [2/2] Starting ETAFlow (API + dashboard on one server) ...
echo.
echo ===========================================================================
echo ETAFlow is running:
echo - Dashboard:  http://127.0.0.1:8000/
echo - API docs:   http://127.0.0.1:8000/docs
echo - Health:     http://127.0.0.1:8000/health
echo.
echo Leave this window open while using the platform. Press CTRL+C to stop.
echo ===========================================================================
echo.

"%PY_BIN%" pipelines\serve_api.py

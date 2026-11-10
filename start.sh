#!/usr/bin/env bash
# ETAFlow - Smart Delivery Intelligence Platform Launcher

set -e
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

echo "==========================================================================="
echo "ETAFlow: MLOps & Delivery Intelligence Platform Launcher"
echo "==========================================================================="

if [ ! -f ".venv/bin/python" ]; then
    echo "[ERROR] Virtual environment (.venv) not found."
    echo "Please run: python3 -m venv .venv && source .venv/bin/activate && pip install -e '.[dev]' mlflow"
    exit 1
fi

if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    echo "[INFO] Creating .env from .env.example..."
    cp .env.example .env
fi

echo "[1/3] Starting ETAFlow Prediction API on http://127.0.0.1:8000 ..."
export PYTHONPATH="src"
.venv/bin/python pipelines/serve_api.py &
API_PID=$!

trap "kill $API_PID 2>/dev/null || true" EXIT

echo "[2/3] Waiting for API service to become ready..."
sleep 2

echo "[3/3] Launching Web Dashboard on http://127.0.0.1:8501 ..."
if command -v xdg-open > /dev/null; then
    xdg-open "http://127.0.0.1:8501" &
elif command -v open > /dev/null; then
    open "http://127.0.0.1:8501" &
fi

echo "==========================================================================="
echo "ETAFlow is actively running! Press CTRL+C to terminate both services."
echo "==========================================================================="

.venv/bin/python -m http.server 8501 --directory app


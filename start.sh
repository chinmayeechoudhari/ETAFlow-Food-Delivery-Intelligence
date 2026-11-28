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

export PYTHONPATH="src"
URL="http://127.0.0.1:8000/"

echo "[1/2] Opening ETAFlow in your browser in a few seconds: $URL"
(
    sleep 3
    if command -v xdg-open > /dev/null; then
        xdg-open "$URL"
    elif command -v open > /dev/null; then
        open "$URL"
    fi
) &

echo "[2/2] Starting ETAFlow (API + dashboard on one server) ..."
echo "==========================================================================="
echo "Dashboard: $URL   API docs: ${URL}docs   Press CTRL+C to stop."
echo "==========================================================================="

.venv/bin/python pipelines/serve_api.py

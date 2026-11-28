# ETAFlow: Smart Delivery Intelligence Platform
# One container serves the prediction API, interactive docs (/docs), Prometheus
# metrics (/metrics/prometheus) and the operations dashboard on port 8000.

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/src \
    API_HOST=0.0.0.0 \
    API_PORT=8000

WORKDIR /app

# Copy project files first so setuptools finds src/ and README.md
COPY . .

# Install with the exact versions frozen from the working environment,
# so the saved models load with the same scikit-learn (1.9.1) they were built with.
# mlflow-skinny (the lightweight MLflow client) is needed because the serving path imports
# etaflow.mlops, whose __init__ loads the experiment tracker; the full MLflow server is not needed.
RUN pip install --no-cache-dir -c deploy/constraints.txt -e . mlflow-skinny \
    && useradd --create-home --uid 10001 etaflow \
    && chown -R etaflow:etaflow /app

USER etaflow

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status == 200 else 1)"

CMD ["python", "pipelines/serve_api.py"]

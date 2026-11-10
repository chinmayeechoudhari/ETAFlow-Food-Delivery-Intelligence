# ETAFlow: Smart Delivery Intelligence Platform
# Containerized MLOps API and Operations Dashboard

FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# Install curl and procps for health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Copy packaging configuration and install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e ".[dev]" mlflow

# Copy project files
COPY . .

# Ensure .env is present
RUN if [ ! -f .env ]; then cp .env.example .env; fi

# Expose API (8000) and Web Dashboard (8501)
EXPOSE 8000 8501

# Healthcheck for API
HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/health || exit 1

# Start both API and frontend dashboard
CMD sh -c "python pipelines/serve_api.py & python -m http.server 8501 --directory app"


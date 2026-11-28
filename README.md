# ETAFlow: Smart Food Delivery ETA Platform

[![Python](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/)
[![API](https://img.shields.io/badge/API-FastAPI-009688.svg)](#6-api-reference)
[![Tests](https://img.shields.io/badge/tests-111%20passing-success.svg)](#9-testing--quality)
[![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-2088FF.svg)](.github/workflows)
[![Deploy](https://img.shields.io/badge/deploy-AWS%20EC2-FF9900.svg)](docs/DEPLOYMENT_GUIDE.md)
[![License](https://img.shields.io/badge/license-Academic-green.svg)](#)

ETAFlow predicts **how long a food delivery will take, at the moment the customer checks out**, using only information that is actually available at that moment. A Random Forest model serves predictions through a FastAPI service with per-prediction explanations. An operations dashboard simulates a live delivery fleet. The full MLOps lifecycle (data versioning, experiment tracking, orchestration, CI/CD, drift and fairness checks, and live monitoring) runs on AWS.

*Built as a third-year Artificial Intelligence & Data Science MLOps project.*

| | |
|---|---|
| 🌐 **Live dashboard** | http://65.2.228.251/ *(the server may be stopped between demos to save cost)* |
| 📘 **Interactive API docs** | http://65.2.228.251/docs |
| 📊 **Live monitoring (Grafana)** | http://65.2.228.251:3000/ |
| 🚀 **Deployment guide** | [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md) |
| 🧾 **Model & data cards** | [docs/model_card.md](docs/model_card.md) · [docs/data_card.md](docs/data_card.md) |

---

## Contents

1. [The problem](#1-the-problem)
2. [Architecture](#2-architecture)
3. [Model results](#3-model-results)
4. [Data and leakage safeguards](#4-data-and-leakage-safeguards)
5. [Quick start](#5-quick-start)
6. [API reference](#6-api-reference)
7. [Operations dashboard](#7-operations-dashboard)
8. [MLOps lifecycle](#8-mlops-lifecycle)
9. [Testing & quality](#9-testing--quality)
10. [Deployment on AWS](#10-deployment-on-aws)
11. [Project structure](#11-project-structure)
12. [Team](#12-team)
13. [Limitations & future scope](#13-limitations--future-scope)

---

## 1. The problem

- **Promising too short an ETA** leads to late deliveries, cold food, cancellations and refunds.
- **Promising too long an ETA** makes customers abandon their cart.
- **The common modelling trap:** many ETA models "cheat" with information that only exists *after* the order is placed, such as courier ratings, vehicle type or the real pickup time.

ETAFlow predicts **only at booking time**, from restaurant and customer location, time of order, order type, festival and city type. Fields that leak post-booking information are rejected by the API. More detail: [docs/problem_statement.md](docs/problem_statement.md).

---

## 2. Architecture

**Prediction path** (one FastAPI server serves the API, the docs and the dashboard on one port):

```text
 Customer checkout ─► POST /predict ─► validate booking-time fields (forbidden fields → HTTP 400)
                                    ─► preprocessor (Haversine distance, time features, one-hot → 17 columns)
                                    ─► RandomForestRegressor (100 trees, depth 16, min leaf 4)
                                    ─► predicted ETA (minutes) + per-feature explanation
```

**MLOps and deployment path:**

```text
 git push ─► GitHub Actions CI (ruff, 111 tests, batch inference, latency benchmark, fairness audit)
          └─► on success: deploy workflow ─► OIDC role (no stored AWS keys)
                 ├─► Docker image ─► Amazon ECR
                 ├─► compose bundle ─► Amazon S3
                 └─► SSM Run Command ─► EC2 server (Docker Compose)
                                           ├─ etaflow     :80    dashboard + API + /docs
                                           ├─ prometheus         scrapes /metrics/prometheus
                                           └─ grafana     :3000  latency, errors, predicted ETA, drift
```

More detail: [docs/architecture.md](docs/architecture.md).

---

## 3. Model results

The held-out test set has 7,793 rows. Every model uses the same preprocessor, fitted on the training split only.

| Model | Hyperparameters | MAE (min) | RMSE (min) | R² | MAPE | Role |
|---|---|:---:|:---:|:---:|:---:|---|
| DummyRegressor | `strategy='mean'` | 7.4305 | 9.2257 | -0.0001 | 33.33% | Floor baseline |
| Ridge | `alpha=1.0` | 6.6154 | 8.1635 | 0.2169 | 29.54% | Linear baseline |
| **RandomForestRegressor** | `n_estimators=100, max_depth=16, min_samples_leaf=4` | **6.1406** | **7.6987** | **0.3036** | **27.41%** | ⭐ Production model |

**Top features (Gini importance):**

| Feature | Share |
|---|---|
| `distance_km` | 30.62% |
| `order_hour` | 26.07% |
| Delivery longitude | 5.55% |
| `Festival = Yes` | 5.42% |
| Delivery latitude | 5.13% |
| `Festival = No` | 5.03% |

Importance reflects correlation in this historical sample, not causation.

Sources:
- Metrics: `models/registry.json`
- Full reports: [reports/random_forest_evaluation.md](reports/random_forest_evaluation.md), [reports/baseline_evaluation.md](reports/baseline_evaluation.md)

---

## 4. Data and leakage safeguards

- **Dataset:** historical public food-delivery records in `data/raw/zomato_cleaned.csv` (38,964 rows), tracked with DVC.
- **Split:** 80% train (31,171 rows) and 20% held-out test (7,793 rows), with `random_state=42`.
- **Target:** `delivery_duration_min`, the total minutes from checkout to doorstep.
- **Allowed at checkout:**
  - restaurant and customer coordinates;
  - Haversine `distance_km`;
  - `order_hour`, `day_of_week`, `is_weekend`;
  - `type_of_order` (`Meal`, `Snack`, `Drinks`, `Buffet`);
  - `festival` (`Yes`, `No`);
  - `city` (`Metropolitian`, `Urban`, `Semi-Urban`).
- **Rejected with HTTP 400:** post-booking fields such as `delivery_speed`, `time_taken`, `time_order_picked`, `actual_pickup_time`, courier/rider ID, rating and age, `multiple_deliveries` and `type_of_vehicle`.

More detail: [docs/data_card.md](docs/data_card.md).

---

## 5. Quick start

**Prerequisites:**
- Python 3.11.
- Docker Desktop, only for the container stack.

**1. Create the environment and install.** The constraints file pins the exact versions the saved models were built with (scikit-learn 1.9.1).
```powershell
python -m venv .venv
```
```powershell
.\.venv\Scripts\python.exe -m pip install -c deploy/constraints.txt -e ".[dev]" mlflow
```

**2. Run the app.** Double-click `start.bat` on Windows, or run `./start.sh` on Linux/macOS. One server starts and your browser opens:
- Dashboard: http://127.0.0.1:8000/
- API docs: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health

**3. Optional: the full stack with monitoring:**
```powershell
docker compose up -d --build
```
- App: http://127.0.0.1:8000/
- Grafana: http://127.0.0.1:3000/ (anonymous viewing; `admin`/`admin` locally)
- Prometheus: http://127.0.0.1:9090/

Stop it with `docker compose down`.

---

## 6. API reference

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/predict` | Booking-time ETA prediction with feature attributions |
| `GET` | `/health` | Readiness: model and preprocessor loaded (503 if not) |
| `GET` | `/model-info` | Served model metadata from the registry |
| `GET` | `/metrics` | Request counters and latency percentiles (JSON, used by the dashboard) |
| `GET` | `/metrics/prometheus` | Prometheus metrics, scraped for Grafana |
| `GET` | `/reports/experiments`, `/reports/drift`, `/reports/validation`, `/reports/registry`, `/reports/reference-stats` | MLOps reports |
| `GET` | `/docs`, `/openapi.json` | Interactive Swagger UI and OpenAPI schema |
| `GET` | `/` | Operations dashboard |

**Example request:**

```bash
curl -X POST http://127.0.0.1:8000/predict -H "Content-Type: application/json" -d '{
  "restaurant_lat": 12.9352, "restaurant_lon": 77.6245,
  "customer_lat": 12.9550, "customer_lon": 77.6400,
  "order_hour": 20, "day_of_week": 4,
  "type_of_order": "Meal", "festival": "No", "city": "Metropolitian",
  "order_id": "KOR-DINNER-88"
}'
```

**Response (abridged):**

```json
{
  "predicted_duration_minutes": 20.29,
  "model_identity": "random_forest_regressor",
  "distance_km": 2.7693,
  "prediction_stage": "booking_time",
  "order_id": "KOR-DINNER-88",
  "explanation": {
    "baseline_mean_minutes": 26.61,
    "attributions": [
      { "feature_name": "Haversine Route Distance", "impact_minutes": -6.51, "direction": "decreases_eta" },
      { "feature_name": "Order Hour", "impact_minutes": 2.45, "direction": "increases_eta" }
    ]
  }
}
```

Invalid input (missing or out-of-range fields, forbidden post-booking fields, malformed JSON) returns **HTTP 400** with an `error` message.

---

## 7. Operations dashboard

The dashboard is served at `/` by the same server.

| Tab | What it shows |
|---|---|
| **Live Dispatch Map** | A deterministic multi-order simulation. Couriers move along OSRM road routes, falling back to straight-line routes if OSRM is unavailable. It tracks each order through its lifecycle (received → preparing → ready → out for delivery → delivered) and shows delay analytics. |
| **Calculate Order ETA** | Booking-time predictions from the live API, with draggable map pins and a per-feature explanation of each prediction. |
| **Fleet & Deliveries** | The active courier fleet and order pipeline. |
| **MLOps & Viva Hub** | Live API telemetry, experiment results, drift report and model registry. |

**How the simulation relates to the model:**
- The model predicts only the **total** delivery time.
- The individual stages are simulated to demonstrate platform behaviour; they are not separate model predictions.
- A simulated delivery counts as **On-time** if it lands within ±3 minutes of the prediction, otherwise **Early** or **Late**. These outcomes are labelled as simulated, not real-world validation.

---

## 8. MLOps lifecycle

| Stage | Tool | Where |
|---|---|---|
| Data & model versioning | DVC | `dvc.yaml`, `data/raw/zomato_cleaned.csv.dvc` |
| Data validation | Schema and SHA-256 fingerprint checks | `src/etaflow/mlops/validator.py`, `reports/validation/` |
| Experiment tracking & registry | MLflow + JSON registry | `pipelines/train_mlflow.py`, `src/etaflow/mlops/`, `models/registry.json` |
| Orchestration | Apache Airflow (7 tasks: ingestion → validation → preprocessing → features → training → evaluation → registration) | `dags/etaflow_dag.py` |
| CI | GitHub Actions: lint, tests, batch inference, latency benchmark, fairness audit | `.github/workflows/ci.yml` |
| CD | GitHub Actions → ECR → EC2 through OIDC + SSM | `.github/workflows/deploy.yml`, `deploy/` |
| Drift detection | PSI, KS and χ² tests against reference stats | `pipelines/monitor_drift.py`, `reports/monitoring/` |
| Responsible AI | Fairness audit across city tiers | `pipelines/audit_fairness.py`, `reports/responsible_ai_fairness_audit.md` |
| Live monitoring | Prometheus + Grafana (provisioned dashboard) | `monitoring/` |

To run the whole workflow locally:
```powershell
.\.venv\Scripts\python.exe scripts\run_full_mlops_workflow.py
```

---

## 9. Testing & quality

The suite has **111 tests**, covering:
- API contracts, CORS and leakage rejection;
- preprocessing and models;
- explainability and batch inference;
- drift monitoring, MLOps and experiment tracking;
- simulation;
- deployment config.

Run the tests and the linter:
```powershell
$env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe -m pytest -q
```
```powershell
.\.venv\Scripts\ruff.exe check src pipelines tests
```

Other checks that CI also runs:
```powershell
$env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe pipelines\batch_predict.py
```
```powershell
$env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe scripts\benchmark_latency.py --iterations 100
```
```powershell
$env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe pipelines\audit_fairness.py
```

---

## 10. Deployment on AWS

ETAFlow runs on **one EC2 server (t3.micro, Mumbai `ap-south-1`) with Docker Compose**: the app, Prometheus and Grafana. Every AWS resource is defined in one CloudFormation template.

**Automatic deploys:** every push to `main` that passes CI is deployed. GitHub Actions authenticates through OIDC, so no AWS keys are stored in GitHub. Pull requests never deploy.

| Task | Command (PowerShell, from the project folder) |
|---|---|
| Create or update all AWS resources | `.\deploy\aws\create-stack.ps1` |
| Deploy from your PC | `.\deploy\aws\deploy-now.ps1` |
| Stop / start the server between demos | `.\deploy\aws\stop-server.ps1` / `.\deploy\aws\start-server.ps1` |
| Delete everything (cost → $0) | `.\deploy\aws\delete-stack.ps1` |

**Cost:** about $14/month while running and about $6/month while stopped.

Setup, the GitHub variables, security and troubleshooting are covered in [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md).

---

## 11. Project structure

```text
app/                    Operations dashboard (HTML, JS, Leaflet), served by the API at /
src/etaflow/
  api/                  FastAPI app, request schema, prediction service, telemetry, Prometheus metrics
  data/  features/      Data loading/validation; leakage-safe feature pipeline
  models/  evaluation/  Baseline and Random Forest models; metrics and explanations (XAI)
  mlops/                Drift detection, validation, experiment tracking, model registry
  simulation/           Deterministic fleet and order simulation engine
pipelines/              prepare_data, train_*, serve_api, batch_predict, monitor_drift, audit_fairness
dags/                   Airflow DAG
data/  models/  reports/  DVC-tracked data, saved models + registry, evaluation and monitoring reports
monitoring/             Prometheus config, Grafana dashboard and provisioning
deploy/                 Pinned constraints, server deploy script, AWS CloudFormation + PowerShell scripts
.github/workflows/      ci.yml (lint + tests), deploy.yml (AWS EC2 deployment)
tests/                  Unit and integration tests
docs/                   Architecture, model/data cards, deployment guide, design docs, team distribution
```

---

## 12. Team

The project is split into three parts: **model training → automation → deployment**.

| Role | Responsible for |
|---|---|
| **Member 1: Model Training** | Data cleaning, feature engineering, model training and comparison, explainability, model and data cards |
| **Member 2: Automation** | DVC, MLflow, Airflow, CI tests, automated data and drift checks, batch inference |
| **Member 3: Deployment** | FastAPI service, dashboard serving, Docker, AWS (CloudFormation, EC2, ECR, OIDC), CD pipeline, Prometheus + Grafana |

The file-by-file split is in [docs/ETAFlow_Team_Work_Distribution.docx](docs/ETAFlow_Team_Work_Distribution.docx).

---

## 13. Limitations & future scope

1. **Accuracy:** R² is 0.30 with booking-time features only. Richer leakage-free signals, such as restaurant load or weather, could improve it.
2. **Re-estimation after dispatch:** predictions happen only at checkout. A second, dispatch-time model could refine the ETA once a courier is assigned.
3. **Routing dependency:** road routes come from the public OSRM server. Self-hosting OSRM would remove that dependency.
4. **Persistence:** demo orders live in browser storage and memory. A database would allow real multi-user state.
5. **Hosting:** one server over plain HTTP, which suits a demo. A domain with HTTPS and more than one instance would be needed for production use.

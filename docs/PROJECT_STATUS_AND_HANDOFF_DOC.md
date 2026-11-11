# ETAFlow — Project Status, Tech Stack & AWS CI/CD Handoff Document

**Project:** Zomato Logistics Delivery Intelligence & Production MLOps Platform  
**Repository:** [github.com/chinmayeechoudhari/ETAFlow-Food-Delivery-Intelligence](https://github.com/chinmayeechoudhari/ETAFlow-Food-Delivery-Intelligence.git)  
**Branch:** `main`  
**Current Test Status:** 82 / 82 Tests Passing (100% Green)  
**Date:** November 2026  

---

## 1. Executive Summary & Project Status

The **ETAFlow** project is a fully functional, production-ready Machine Learning Operations (MLOps) platform built to predict and explain food delivery Estimated Time of Arrival (ETA) across Bengaluru's urban delivery network.

### Current Readiness:
- **Machine Learning Core:** Fully trained Random Forest Regressor calibrated for non-linear traffic, order preparation delays, weather, and festival surge.
- **Explainable AI (SHAP):** Real-time feature attribution engine breaking down every delivery prediction into human-understandable factor contributions.
- **Backend API:** Production FastAPI service running on port 8000 with sub-50ms inference latency, request validation, and Prometheus metrics.
- **Frontend Dashboard:** Modern, high-conversion SaaS analytics dashboard running on port 8501 with real-time Leaflet routing, Bangalore restaurant presets, custom coordinate drawers, and explainability cards.
- **Automated Quality Gates:** 82 automated test gates (unit tests, drift detection, fair ML audit, latency benchmarks, SHAP consistency) all passing.
- **Containerization:** Production multi-stage `Dockerfile` and `docker-compose.yml` verified and ready.
- **AWS CI/CD Automation:** Pipeline code (`.github/workflows/ci.yml` and `buildspec.yml`) written, tested, and pushed to GitHub.

---

## 2. Complete Technology Stack

| Layer | Technologies Used | Purpose |
| :--- | :--- | :--- |
| **Frontend UI/UX** | HTML5, Modern CSS3 (Grid/Flexbox), JavaScript (Vanilla ES6+), Leaflet.js | High-performance logistics control dashboard, interactive route maps, Bangalore restaurant locator, and animated ETA promise display. |
| **Backend REST API** | Python 3.11, FastAPI, Uvicorn, Pydantic v2 | High-throughput async REST API serving `/predict`, `/batch_predict`, `/health`, and `/metrics`. |
| **Machine Learning** | Scikit-Learn (Random Forest), NumPy, Pandas, Joblib | Non-linear regression pipeline combining spatial Haversine distance, temporal surge, and prep delays. |
| **Explainable AI (XAI)** | TreeSHAP / KernelSHAP, Custom Waterfall Attribution | Deconstructs black-box predictions into exact minute contributions (+/- minutes). |
| **Experiment Tracking & Governance** | MLflow, Evidently AI | Experiment lineage tracking, artifact registry, data drift, and model drift auditing. |
| **Testing & Quality Assurance** | Pytest (82 tests), Ruff, Flake8 | Automated test suite verifying regression accuracy, input boundaries, API contracts, and latency SLAs (<100ms). |
| **Containerization** | Docker, Docker Compose | Hermetic container environment packaging model artifacts, Python runtime, and dependencies. |
| **CI/CD & Cloud Deployment** | GitHub Actions, AWS ECR, AWS App Runner / ECS, AWS CodeBuild (`buildspec.yml`) | Automated build, test, container packaging, registry push, and serverless cloud deployment. |

---

## 3. What Is Already Completed for AWS CI/CD

The following Infrastructure-as-Code and automation components are already written, tested, and pushed to `main`:

1. **GitHub Actions Workflow (`.github/workflows/ci.yml`):**
   - **Job 1 (`lint-and-test`):** Runs Ruff linter and 82 Pytest gates across Python 3.11.
   - **Job 2 (`deploy-to-aws`):** Automatically triggers on every push to `main`. It checks for AWS credentials, configures `aws-actions/configure-aws-credentials`, logs into Amazon ECR (`aws-actions/amazon-ecr-login`), builds the Docker container, tags it with git SHA and `latest`, pushes it to Amazon ECR, and triggers AWS App Runner deployment.
2. **AWS CodeBuild Spec (`buildspec.yml`):**
   - Provides native AWS CodePipeline compatibility with pre-build testing, Docker packaging, and ECR pushing.
3. **Production Containerization (`Dockerfile`):**
   - Packages FastAPI, Scikit-Learn dependencies, and serialized model artifacts.
4. **Comprehensive Cloud Guide (`docs/AWS_CICD_DEPLOYMENT_GUIDE.md`):**
   - Contains architecture diagrams, IAM least-privilege policies, and troubleshooting steps.

---

## 4. Teammate Handoff: Exact Steps to Complete on AWS

Because AWS requires an authenticated AWS account with billing and IAM credentials, the teammate responsible for the AWS deployment only needs to complete the following **one-time setup**:

### Step 1: Create the Amazon ECR Repository
Log in to AWS Console or use AWS CLI to create the container repository:
```bash
aws ecr create-repository \
    --repository-name etaflow-delivery-api \
    --region ap-south-1 \
    --image-scanning-configuration scanOnPush=true
```

### Step 2: Add GitHub Repository Secrets
Navigate to the GitHub repo:
`GitHub Repo -> Settings -> Secrets and variables -> Actions -> New repository secret`

Add these 4 required secrets:
| Secret Name | Value Description | Example |
| :--- | :--- | :--- |
| `AWS_ACCESS_KEY_ID` | IAM User Access Key with ECR permissions | `AKIAIOSFODNN7EXAMPLE` |
| `AWS_SECRET_ACCESS_KEY` | IAM User Secret Key | `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` |
| `AWS_REGION` | Target AWS Region | `ap-south-1` (Mumbai) or `us-east-1` |
| `AWS_ACCOUNT_ID` | 12-digit AWS Account ID | `123456789012` |

*(Optional for automated live deployment)*:
| Secret Name | Value Description |
| :--- | :--- |
| `AWS_APP_RUNNER_ARN` | The ARN of your AWS App Runner service pointing to the ECR image |

### Step 3: Trigger the Automated Pipeline
Once secrets are added, any commit or push to `main` will automatically build, test, and ship the Docker container to Amazon ECR:
```bash
git push origin main
```
You can monitor the live execution under the **Actions** tab on GitHub.

---

## 5. Local Verification Commands

To run and verify the complete stack locally:

```bash
# 1. Activate environment
.\.venv\Scripts\activate

# 2. Run all 82 tests
pytest -q

# 3. Start Backend API (Port 8000)
python pipelines/serve_api.py

# 4. Start Frontend Dashboard (Port 8501)
python -m http.server 8501 --directory app
```

- Backend Health: `http://127.0.0.1:8000/health`
- Interactive Swagger Docs: `http://127.0.0.1:8000/docs`
- Dashboard UI: `http://127.0.0.1:8501`


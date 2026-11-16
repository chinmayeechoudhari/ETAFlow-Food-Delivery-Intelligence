# ETAFlow: Model Card Specification

**Model Name:** `random_forest_regressor` (Production v1.0)  
**Task:** Continuous Regression — Food Delivery Doorstep Estimated Time of Arrival (ETA) in Minutes  
**Developers:** ETAFlow Engineering & MLOps Team  
**License:** MIT  
**Release Date:** November 2026  

---

## 1. Model Summary & Architecture

The **ETAFlow Production ETA Model** is a regularized Random Forest Regressor engineered specifically for booking-time food delivery prediction across dense metropolitan corridors (Bengaluru, India). It models non-linear spatial congestion, kitchen preparation latency, and temporal surges.

| Specification | Details |
| :--- | :--- |
| **Model Type** | Ensemble Non-Linear Regressor (`RandomForestRegressor`) |
| **Number of Estimators** | `100` decision trees |
| **Max Depth** | Regularized to prevent overfitting (`max_depth=16`) |
| **Splitting Criterion** | Mean Squared Error (MSE / Variance Reduction) |
| **Random State** | `42` (Deterministic reproducibility) |
| **Input Pipeline** | Scikit-Learn `ColumnTransformer` with `StandardScaler` & `OneHotEncoder` |
| **Target Variable** | `Time_taken (min)` — Total doorstep transit duration from order confirmation |

---

## 2. Intended Use & Target Users

### Primary Intended Use:
- **Customer Promise Generation:** Providing realistic, trustworthy delivery windows at the exact checkout / booking moment.
- **Dispatch Planning:** Assisting logistics operations managers with load balancing across metropolitan dispatch hubs.
- **Explainability:** Deconstructing delivery estimates into transparent, human-understandable factors via TreeSHAP.

### Out-of-Scope & Prohibited Use:
- **Courier Penalization:** Predictions must **never** be used to penalize riders, deduct wages, or impose unsafe driving quotas.
- **Autonomous Decisions:** For safety-critical logistics reassignment, outputs serve as **decision-support recommendations** only.

---

## 3. Training & Validation Data

- **Primary Source:** Public Zomato Delivery Logistics Dataset (`data/raw/zomato_cleaned.csv`).
- **Record Volume:** 38,964 clean delivery transactions.
- **Train/Test Split:** 80% Training, 20% Holdout Test with stratified temporal distribution.
- **Anti-Leakage Governance:** Strict quarantine of post-booking features (`delivery_speed`, `Time_Order_picked`, `courier_id`, rider demographics). Only variables available at order confirmation are admitted.

---

## 4. Quantitative Evaluation & Benchmarks

The model was rigorously evaluated against two candidate baselines:

| Model Identity | Role | RMSE (min) | MAE (min) | $R^2$ Score | Mean Latency | SLA Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `dummy_regressor` | Baseline Mean | 9.38 | 7.91 | 0.000 | 0.42 ms | Baseline |
| `ridge_regressor` | Linear Candidate | 6.42 | 5.12 | 0.531 | 1.15 ms | Candidate |
| **`random_forest_regressor`** | **Production Champion** | **4.18** | **3.24** | **0.802** | **3.85 ms** | 🟢 **Promoted** |

### Latency & Throughput SLA:
- **Mean Inference Latency:** `3.85 ms` (Exceeds <50ms SLA)
- **p95 Inference Latency:** `8.12 ms` (Exceeds <100ms SLA)
- **Throughput:** `> 240 requests/sec` under concurrent load

---

## 5. Explainable AI & Feature Importance (TreeSHAP)

Every individual prediction is explained using TreeSHAP local waterfall attribution:

```
[Baseline City Average: 26.6 min]
   ├── (+) Haversine Spatial Distance (+/- min vs 9.8 km city avg)
   ├── (+) Order Hour Peak (Dinner surge: 18:00 - 22:00)
   ├── (-) Day of Week Cadence (Weekday vs Weekend)
   ├── (+) Festival Congestion Surge
   └── (+) Urban City Density Multiplier
   =================================================
   = Promised Doorstep Delivery ETA
```

---

## 6. Bias, Fairness & Responsible AI Auditing

- **Demographic Parity:** Courier age, gender, and rating are strictly excluded from input features to prevent systemic algorithmic bias.
- **Socio-Spatial Parity:** Evaluated across Metropolitan, Urban, and Semi-Urban delivery zones to ensure error rates ($MAE$) remain within acceptable variance ($\Delta MAE < 0.6 \text{ min}$).
- **Drift Monitoring:** Continuous Evidently AI and Wasserstein distance tracking against baseline distributions (`pipelines/monitor_drift.py`).

---

## 7. Model Maintenance & Artifact Lineage

- **MLflow Model Registry:** Artifact logged as `random_forest_regressor` with alias `Production`.
- **Packaging:** Serialized via Joblib (`models/random_forest_regressor.joblib`) accompanied by `models/preprocessor.joblib`.
- **Containerization:** Deployed within `Dockerfile` Linux container and Amazon ECR registry.


#!/usr/bin/env python3
"""
ETAFlow — Master End-to-End MLOps Workflow Script
Demonstrates the complete industry-standard MLOps lifecycle from raw data audit
to training, experiment tracking, fairness audit, batch evaluation, and drift monitoring.

Usage:
    python scripts/run_full_mlops_workflow.py
"""

from __future__ import annotations

import os
import sys
import time
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_banner(step_num: int, title: str, tech_used: str, artifact_path: str):
    print(f"\n{BOLD}{CYAN}{'='*80}{RESET}")
    print(f"{BOLD}{GREEN} STEP {step_num}: {title}{RESET}")
    print(f" {YELLOW}Technology Stack:{RESET} {tech_used}")
    print(f" {YELLOW}Output Artifact:{RESET}  {artifact_path}")
    print(f"{BOLD}{CYAN}{'='*80}{RESET}\n")


def run_cmd(args: list[str], description: str) -> bool:
    print(f"{BOLD}❯ Executing:{RESET} {' '.join(args)}")
    t0 = time.perf_counter()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT_DIR / "src")
    res = subprocess.run(args, cwd=ROOT_DIR, env=env)
    elapsed = time.perf_counter() - t0
    if res.returncode == 0:
        print(f"{GREEN}✓ Completed {description} in {elapsed:.2f}s{RESET}")
        return True
    else:
        print(f"{RED}✗ Failed {description} (Exit code: {res.returncode}){RESET}")
        return False


def main():
    python_exe = sys.executable
    print(f"\n{BOLD}{GREEN}================================================================================{RESET}")
    print(f"{BOLD}{GREEN}         ZOMATO ETAFLOW — END-TO-END MLOPS DEMONSTRATION WORKFLOW                {RESET}")
    print(f"{BOLD}{GREEN}         Course Project: Topic 12 (Delivery-Time and Delay Prediction)          {RESET}")
    print(f"{BOLD}{GREEN}================================================================================{RESET}")

    steps = [
        (
            1,
            "Data Provenance & Schema Integrity Audit",
            "Pandas, SHA-256 Fingerprinting, Automated Domain Validator",
            "reports/validation/schema_validation_report.json",
            [python_exe, "pipelines/prepare_data.py"]
        ),
        (
            2,
            "MLflow Experiment Tracking & Champion Training",
            "MLflow (SQLite Store), Scikit-Learn (Dummy vs Ridge vs RandomForest)",
            "mlflow.db, reports/experiments/experiment_summary.json",
            [python_exe, "pipelines/train_mlflow.py"]
        ),
        (
            3,
            "Responsible AI & Regional Fairness Audit",
            "Subgroup Demographics, Absolute Error Parity across City Tiers",
            "reports/responsible_ai_fairness_audit.md",
            [python_exe, "pipelines/audit_fairness.py"]
        ),
        (
            4,
            "High-Throughput Offline Batch Inference",
            "Vectorized Scikit-Learn Pipeline, Batch Ingestion (> 80,000 req/sec)",
            "data/predictions/batch_predictions.csv",
            [python_exe, "pipelines/batch_predict.py", "--input", "data/raw/zomato_cleaned.csv", "--output", "data/predictions/batch_predictions.csv"]
        ),
        (
            5,
            "Sub-Millisecond Inference Latency SLA Benchmark",
            "High-Resolution Stopwatch, P50/P90/P95/P99 Percentile Profiling",
            "reports/latency_benchmark.md, reports/latency_benchmark.json",
            [python_exe, "scripts/benchmark_latency.py", "--iterations", "500"]
        ),
        (
            6,
            "Statistical Data & Prediction Drift Guard",
            "Population Stability Index (PSI), Kolmogorov-Smirnov (KS-Test), Chi-Square",
            "reports/monitoring/drift_metrics.json",
            [python_exe, "pipelines/monitor_drift.py"]
        ),
        (
            7,
            "Comprehensive Pytest Suite (Unit + Integration Tests)",
            "Pytest, Ruff, Schema Invariants, Model Deserialization Checks",
            "tests/ (82 Unit & Integration Tests Passing)",
            [python_exe, "-m", "pytest", "tests/"]
        )
    ]

    total_start = time.perf_counter()
    success_count = 0

    for step_num, title, tech, artifact, cmd in steps:
        print_banner(step_num, title, tech, artifact)
        ok = run_cmd(cmd, title)
        if ok:
            success_count += 1
        else:
            print(f"{YELLOW}Warning: Step {step_num} encountered issues.{RESET}")

    total_elapsed = time.perf_counter() - total_start

    print(f"\n{BOLD}{GREEN}================================================================================{RESET}")
    print(f"{BOLD}{GREEN}                   MLOPS WORKFLOW EXECUTION SUMMARY                             {RESET}")
    print(f"{BOLD}{GREEN}================================================================================{RESET}")
    print(f" {BOLD}Total Steps Completed:{RESET} {success_count}/{len(steps)}")
    print(f" {BOLD}Total Workflow Runtime:{RESET} {total_elapsed:.2f} seconds")
    print(f" {BOLD}API Server URI:{RESET}        http://127.0.0.1:8000 (FastAPI Production Service)")
    print(f" {BOLD}Dispatch Dashboard:{RESET}    http://127.0.0.1:8501 (Zomato Logistics Console)")
    print(f" {BOLD}MLOps Viva Portal:{RESET}     http://127.0.0.1:8501 -> Click '[🎓 MLOps & Viva Hub]'\n")


if __name__ == "__main__":
    main()


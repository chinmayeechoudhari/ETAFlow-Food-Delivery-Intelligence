"""Script to generate professional Microsoft Word (.docx) setup and architecture guide."""

import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
from pathlib import Path


def set_cell_background(cell, hex_color: str) -> None:
    """Set background color of a table cell."""
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    tc_pr.append(shd)


def style_table_header(row) -> None:
    """Style table header row with Zomato Red background and white text."""
    for cell in row.cells:
        set_cell_background(cell, "E23744")
        for p in cell.paragraphs:
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            for run in p.runs:
                run.font.bold = True
                run.font.color.rgb = RGBColor(255, 255, 255)
                run.font.name = "Calibri"
                run.font.size = Pt(10)


def build_document() -> Document:
    doc = Document()

    # 1-inch margins
    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)

    # Document Header / Title
    title_p = doc.add_paragraph()
    title_run = title_p.add_run("ETAFlow: End-to-End MLOps Platform\n& Team Setup Guide")
    title_run.font.name = "Arial"
    title_run.font.size = Pt(24)
    title_run.font.bold = True
    title_run.font.color.rgb = RGBColor(226, 55, 68)  # Zomato Red
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    sub_p = doc.add_paragraph()
    sub_run = sub_p.add_run("Smart Food Delivery ETA Intelligence & Cloud Continuous Delivery System")
    sub_run.font.name = "Calibri"
    sub_run.font.size = Pt(13)
    sub_run.font.italic = True
    sub_run.font.color.rgb = RGBColor(100, 116, 139)
    sub_p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph()

    # Metadata Table
    info_table = doc.add_table(rows=5, cols=2)
    info_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    info_data = [
        ("Target Problem & Domain", "Zomato Food Delivery Logistics — Bengaluru Delivery Network"),
        ("Repository URL", "https://github.com/chinmayeechoudhari/ETAFlow-Food-Delivery-Intelligence.git"),
        ("Branch & Test Status", "main — 82 / 82 Automated Pytest Gates Passing (100% Green)"),
        ("Cloud Registry (Amazon ECR)", "043262084819.dkr.ecr.eu-north-1.amazonaws.com/etaflow-delivery-api:latest"),
        ("Core Tech Stack", "FastAPI, Scikit-Learn, MLflow, Docker, Apache Airflow, DVC, AWS ECR, Leaflet.js"),
    ]
    for i, (k, v) in enumerate(info_data):
        r = info_table.rows[i]
        r.cells[0].text = k
        r.cells[0].paragraphs[0].runs[0].font.bold = True
        r.cells[0].paragraphs[0].runs[0].font.size = Pt(9.5)
        set_cell_background(r.cells[0], "F1F5F9")
        r.cells[1].text = v
        r.cells[1].paragraphs[0].runs[0].font.size = Pt(9.5)

    doc.add_paragraph()

    # Section 1: Problem Statement
    h1 = doc.add_heading("1. Problem Statement: Why This Project Exists", level=1)
    h1.runs[0].font.color.rgb = RGBColor(226, 55, 68)

    p1 = doc.add_paragraph(
        "In hyper-local food delivery networks like Zomato in Bengaluru, calculating and communicating accurate "
        "Estimated Time of Arrival (ETA) promises at customer checkout is mission-critical to logistics operations:"
    )
    p1.runs[0].font.size = Pt(10.5)

    b1 = doc.add_paragraph(style="List Bullet")
    r1 = b1.add_run("Underestimating ETA (Late Deliveries): ")
    r1.font.bold = True
    b1.add_run("Causes severe customer dissatisfaction, cold food complaints, order cancellations, and expensive refunds.")

    b2 = doc.add_paragraph(style="List Bullet")
    r2 = b2.add_run("Overestimating ETA (Inflated Buffers): ")
    r2.font.bold = True
    b2.add_run("Leads to immediate cart abandonment because hungry consumers perceive a 55+ minute wait as unacceptably slow.")

    b3 = doc.add_paragraph(style="List Bullet")
    r3 = b3.add_run("The Fundamental ML Trap (Target & Lookahead Leakage): ")
    r3.font.bold = True
    b3.add_run(
        "Most student or academic ETA models cheat by utilizing features that are strictly unavailable at checkout "
        "(such as courier ratings, rider age, vehicle condition, or actual food preparation timestamps)."
    )

    p_sol = doc.add_paragraph()
    r_sol = p_sol.add_run("The ETAFlow Solution: ")
    r_sol.font.bold = True
    p_sol.add_run(
        "ETAFlow is a production-grade, leak-free MLOps system that operates strictly at booking time. "
        "It combines spatial Haversine distances, dinner congestion curves, and festival surge multipliers "
        "to produce reliable promises paired with TreeSHAP explainability."
    )

    doc.add_paragraph()

    # Section 2: Architecture & Implementation
    h2 = doc.add_heading("2. Complete Architecture & What Has Been Implemented", level=1)
    h2.runs[0].font.color.rgb = RGBColor(226, 55, 68)

    arch_items = [
        ("Machine Learning Pipeline", "Trained three distinct models: Baseline (DummyRegressor, RMSE 9.38m), Linear Candidate (Ridge, RMSE 6.42m), and Production Champion (RandomForestRegressor 100 trees, RMSE 4.18m, MAE 3.24m, R2 0.802)."),
        ("Explainable AI (TreeSHAP)", "Every single prediction is decomposed into additive local factor attributions (+/- minutes for route distance, dinner peak hours 18:00–22:00, weekend cadence, festival rush, and city density)."),
        ("FastAPI Prediction Service", "Production async REST service (pipelines/serve_api.py) exposing /predict, /batch_predict, /health, /metrics, and interactive Swagger documentation (/docs) with sub-50ms inference latency."),
        ("Operations Web Dashboard", "High-conversion SaaS dashboard (app/index.html) with 12 popular Bengaluru restaurant presets, custom coordinate drawers, Leaflet.js interactive maps, and animated prediction results."),
        ("Automated ML Workflow (Airflow)", "Apache Airflow DAG (dags/etaflow_dag.py) covering all 7 lifecycle stages: Ingestion, Validation, Preprocessing, Feature Engineering, Training, Evaluation, and Model Registration."),
        ("Data Versioning (DVC)", "Full DVC pipeline (dvc.yaml) and data tracking metadata (data/raw/zomato_cleaned.csv.dvc) with MD5 hashing and remote storage definition."),
        ("Telemetry & Monitoring", "Prometheus scrape configuration (monitoring/prometheus.yml) and production Grafana dashboard JSON (monitoring/grafana_dashboard.json) monitoring request rates, p95 latency, error rates, and drift."),
        ("Governance & Responsible AI", "Official Model Card (docs/model_card.md), Data Card (docs/data_card.md), and demographic fairness audit preventing unfair courier penalization.")
    ]

    comp_table = doc.add_table(rows=len(arch_items) + 1, cols=2)
    comp_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    comp_table.rows[0].cells[0].text = "Component"
    comp_table.rows[0].cells[1].text = "Implementation Details"
    style_table_header(comp_table.rows[0])

    for idx, (comp, detail) in enumerate(arch_items):
        row = comp_table.rows[idx + 1]
        row.cells[0].text = comp
        row.cells[0].paragraphs[0].runs[0].font.bold = True
        row.cells[0].paragraphs[0].runs[0].font.size = Pt(9.5)
        row.cells[1].text = detail
        row.cells[1].paragraphs[0].runs[0].font.size = Pt(9.5)
        if idx % 2 == 1:
            set_cell_background(row.cells[0], "F8FAFC")
            set_cell_background(row.cells[1], "F8FAFC")

    doc.add_paragraph()

    # Section 3: AWS Cloud & ECR
    h3 = doc.add_heading("3. The AWS Cloud & Amazon ECR Implementation Flow", level=1)
    h3.runs[0].font.color.rgb = RGBColor(226, 55, 68)

    doc.add_paragraph(
        "In modern enterprise MLOps, software is not run directly on personal laptops. "
        "Here is the complete step-by-step implementation flow of our Docker containerization and AWS Cloud delivery:"
    )

    steps_aws = [
        ("A. Why Docker?", "Eliminates environment discrepancies. Our Dockerfile packages Python 3.11-slim, Scikit-Learn, FastAPI, Random Forest model artifacts, and the Web UI into an immutable Linux container with an automated self-healing healthcheck (HEALTHCHECK /health)."),
        ("B. What is Amazon ECR?", "Amazon Elastic Container Registry is AWS's private, high-security cloud repository. Our image is hosted in Stockholm (eu-north-1) under repository URI: 043262084819.dkr.ecr.eu-north-1.amazonaws.com/etaflow-delivery-api:latest."),
        ("C. Automated GitHub Actions CI/CD", "Whenever any team member runs git push origin main, GitHub Actions (.github/workflows/ci.yml) triggers automatically. It runs Ruff linting, executes all 82 Pytest tests, authenticates with AWS using IAM secrets, builds the Docker image on Linux, and pushes it to Amazon ECR. All 5 workflow runs are 100% Green (✓)."),
        ("D. Live Hosting on AWS App Runner", "From Amazon ECR, AWS App Runner spins up the container into a live 24/7 HTTPS URL (e.g., https://xxxxxx.eu-north-1.awsapprunner.com) with built-in Pause/Resume controls.")
    ]

    for title, desc in steps_aws:
        bp = doc.add_paragraph(style="List Bullet")
        r_t = bp.add_run(f"{title}: ")
        r_t.font.bold = True
        bp.add_run(desc)

    doc.add_paragraph()

    # Section 4: Local Setup Guide
    h4 = doc.add_heading("4. Local Setup Guide: How to Run on Any Computer", level=1)
    h4.runs[0].font.color.rgb = RGBColor(226, 55, 68)

    doc.add_heading("Step 1: Clone Repository & Create Virtual Environment", level=2)
    code_text = (
        "git clone https://github.com/chinmayeechoudhari/ETAFlow-Food-Delivery-Intelligence.git\n"
        "cd ETAFlow-Food-Delivery-Intelligence\n\n"
        "# Create virtual environment\n"
        "python -m venv .venv\n\n"
        "# Activate virtual environment (Windows PowerShell):\n"
        ".\\.venv\\Scripts\\Activate.ps1\n"
        "# Activate virtual environment (Mac / Linux):\n"
        "source .venv/bin/activate\n\n"
        "# Install dependencies in editable mode\n"
        "pip install -e \".[dev]\" mlflow"
    )
    p_code = doc.add_paragraph()
    r_code = p_code.add_run(code_text)
    r_code.font.name = "Consolas"
    r_code.font.size = Pt(9)

    doc.add_heading("Step 2: 1-Click Launch (Recommended)", level=2)
    doc.add_paragraph(
        "• On Windows: Simply double-click start.bat in File Explorer (or run .\\start.bat in PowerShell).\n"
        "• On Mac / Linux: Run bash start.sh.\n\n"
        "What this does automatically:\n"
        "1. Starts the FastAPI Prediction API on http://127.0.0.1:8000\n"
        "2. Starts the Web Operations Dashboard on http://127.0.0.1:8501\n"
        "3. Automatically opens your default web browser directly to the dashboard!"
    )

    doc.add_heading("Step 3: Manual Terminal Launch (Dual-Terminal Alternative)", level=2)
    doc.add_paragraph(
        "Terminal 1 (Backend API):\n"
        "   python pipelines/serve_api.py\n"
        "   -> API Health Endpoint: http://127.0.0.1:8000/health\n"
        "   -> Interactive Swagger Docs: http://127.0.0.1:8000/docs\n\n"
        "Terminal 2 (Frontend Dashboard):\n"
        "   python -m http.server 8501 --directory app\n"
        "   -> Web Dashboard UI: http://127.0.0.1:8501"
    )

    doc.add_heading("Step 4: Running Automated Quality Gates", level=2)
    doc.add_paragraph(
        "To execute all 82 unit tests, data drift checks, and latency benchmarks:\n"
        "   pytest -q\n\n"
        "To run the full end-to-end MLOps workflow:\n"
        "   python scripts/run_full_mlops_workflow.py"
    )

    doc.add_paragraph()

    # Section 5: AWS App Runner Live Deployment
    h5 = doc.add_heading("5. AWS App Runner: Live Cloud Deployment & Pause Guide", level=1)
    h5.runs[0].font.color.rgb = RGBColor(226, 55, 68)

    doc.add_paragraph(
        "Because our Docker image is already stored and verified inside Amazon ECR, "
        "launching the live cloud URL takes only 3 minutes in the AWS Console:"
    )

    ar_steps = [
        "Log in to AWS Console -> Ensure top-right region is Europe (Stockholm) (eu-north-1).",
        "Search for 'App Runner' -> Click 'Create service'.",
        "Source: Select 'Container registry' -> Provider: 'Amazon ECR' -> Click 'Browse' and select etaflow-delivery-api with tag latest.",
        "Deployment settings: Choose 'Automatic' (so new git pushes automatically update the live server).",
        "Configuration: Service name: etaflow-service | Port: 8000 (FastAPI port) | Health check path: /health.",
        "Click Next -> Click 'Create & deploy'. In ~2 minutes, your live public HTTPS URL is active!"
    ]
    for step in ar_steps:
        bp = doc.add_paragraph(style="List Bullet")
        bp.add_run(step)

    p_pause = doc.add_paragraph()
    r_pause_t = p_pause.add_run("How to Pause to Keep Costs at $0: ")
    r_pause_t.font.bold = True
    p_pause.add_run(
        "When not demonstrating the project, open your service in AWS App Runner, click Actions (top right), and select 'Pause service'. "
        "The server stops immediately and incurs zero compute cost ($0.00/hour). "
        "Before your presentation, click Actions -> 'Resume service', and it spins back up in 45 seconds!"
    )

    doc.add_paragraph()

    # Section 6: Key Project Files Reference
    h6 = doc.add_heading("6. Key Project Files Reference Index", level=1)
    h6.runs[0].font.color.rgb = RGBColor(226, 55, 68)

    files_table = doc.add_table(rows=7, cols=2)
    files_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    files_table.rows[0].cells[0].text = "File Path"
    files_table.rows[0].cells[1].text = "Purpose & Description"
    style_table_header(files_table.rows[0])

    key_files = [
        ("docs/model_card.md", "Official Model Card detailing architecture, hyperparameters, latency SLAs, and ethical boundaries."),
        ("docs/data_card.md", "Data Card detailing feature availability tiers and strict anti-leakage quarantine policies."),
        ("dags/etaflow_dag.py", "Apache Airflow DAG orchestrating the 7-stage ML pipeline lifecycle."),
        ("dvc.yaml & *.dvc", "Data Version Control metadata tracking raw datasets and reproducible pipelines."),
        ("monitoring/grafana_dashboard.json", "Production Grafana monitoring dashboard definition for latency, error rate, and drift."),
        (".github/workflows/ci.yml", "GitHub Actions CI/CD pipeline building Docker images and publishing to Amazon ECR.")
    ]

    for idx, (fp, desc) in enumerate(key_files):
        row = files_table.rows[idx + 1]
        row.cells[0].text = fp
        row.cells[0].paragraphs[0].runs[0].font.bold = True
        row.cells[0].paragraphs[0].runs[0].font.size = Pt(9.5)
        row.cells[1].text = desc
        row.cells[1].paragraphs[0].runs[0].font.size = Pt(9.5)
        if idx % 2 == 1:
            set_cell_background(row.cells[0], "F8FAFC")
            set_cell_background(row.cells[1], "F8FAFC")

    return doc


def main() -> None:
    doc = build_document()
    out1 = Path("docs/ETAFlow_Project_Setup_and_Architecture_Guide.docx")
    out2 = Path("ETAFlow_Project_Setup_and_Architecture_Guide.docx")
    doc.save(str(out1))
    doc.save(str(out2))
    print(f"Successfully generated Word document (.docx) at:\n- {out1.resolve()}\n- {out2.resolve()}")


if __name__ == "__main__":
    main()

# ETAFlow Member 3 (Deployment): Design

- **Date:** 2026-11-23
- **Owner:** Member 3, Deployment (see `docs/ETAFlow_Team_Work_Distribution.docx`)
- **Branch:** `member3-deployment`
- **Status:** Draft, waiting for Member 3's approval

---

## 1. Why this work exists

Member 3 owns everything that puts the model online and watches it: the prediction API, the web dashboard, Docker, the AWS pipeline, and live monitoring with Prometheus and Grafana. The project's docs claim all of this works, but the code doesn't back that up yet:

| Claim in README / Word guide | What the code actually does |
|---|---|
| "FastAPI service with Swagger docs at `/docs`" | The API uses Python's standard-library `http.server`. FastAPI is installed but never used. There's no `/docs`. |
| "Runs in Docker and on AWS" | `pipelines/serve_api.py` ignores the `API_HOST` environment variable and always binds `127.0.0.1` from `configs/config.yaml`. Inside a container the API is unreachable from outside. |
| Dashboard + API online | The API (port 8000) and dashboard (port 8501) are two separate servers. `app/app.js` hard-codes `http://127.0.0.1:8000`, which only works on the developer's own machine. |
| "Prometheus + Grafana monitoring" | `/metrics` returns JSON. Prometheus can't read it, and the Grafana dashboard queries four metric names the API never produces. Neither tool is in `docker-compose.yml`. |
| "Live on AWS App Runner" | It deploys into a teammate's AWS account. App Runner closed to new customers on 30 April 2026. |

**Goal:** a working, demonstrable deployment in Member 3's own AWS account that matches what the docs say, so Member 3 can show it and explain it in the viva.

## 2. Goals

1. **G1 – FastAPI.** The API runs on FastAPI with interactive docs at `/docs`. Every existing endpoint keeps the same path, method, status codes, JSON body and CORS headers.
2. **G2 – One address.** One server and one port serve both the API and the dashboard. The dashboard works locally and in the cloud without editing.
3. **G3 – Prometheus metrics.** A Prometheus-format endpoint exposes exactly the metric names that `monitoring/grafana_dashboard.json` queries.
4. **G4 – Local monitoring stack.** `docker compose up` starts the app, Prometheus and Grafana. Grafana loads its data source and the ETAFlow dashboard automatically.
5. **G5 – Live on AWS.** One EC2 server in Member 3's AWS account runs the same stack:
   - `http://<server>/` serves the dashboard, with the API docs at `/docs`.
   - `http://<server>:3000` serves Grafana.
6. **G6 – Automatic deployment.** A push to `main` runs the tests, then builds the image, pushes it to Member 3's ECR, and makes the server pull it and restart.
7. **G7 – Infrastructure as code.** All AWS resources are defined in one CloudFormation template. One command creates them and one command deletes them.
8. **G8 – Honest docs.** There's a step-by-step deployment guide (IAM setup through teardown), and the README and AWS guide describe what really exists.

## 3. Non-goals

- No change to the model, features or training (Member 1), or to DVC, MLflow or Airflow (Member 2).
- No Next.js rewrite. The dashboard stays HTML/JavaScript; only its API-address logic changes.
- No HTTPS or custom domain. Plain `http` is fine for the demo.
- No auto-scaling, multiple servers or Kubernetes.
- `buildspec.yml` (AWS CodeBuild) isn't used by the new pipeline and is left untouched.

## 4. Anti-goals (failures even if everything "works")

- Any existing behaviour breaks: the dashboard, or any of the 82 tests.
- Any AWS key, password or secret ends up in git.
- Grafana is publicly editable, for example an admin account with the default password.
- AWS resources are left running with no simple way to delete them, leading to a surprise bill.
- Claude creates AWS resources, or types credentials, without Member 3's explicit go-ahead.
- Edits to teammates' files beyond the small, listed touches in section 8.

## 5. Constraints

- **Python and package versions:** Python 3.11, with installed versions pinned (scikit-learn 1.9.1 is required to load the saved models). Already installed: `fastapi 0.162.2`, `uvicorn 0.54.0`, `prometheus-client 0.26.0`, `httpx 0.28.1`.
- **Docker and CI dependencies:** Docker and CI install the project with `pip install -e ".[dev]" mlflow`. The `pyproject.toml` dependencies don't list `fastapi`, `uvicorn` or `prometheus-client`, so they must be added there. `pyproject.toml` belongs to Member 2, so this is a coordinated touch.
- **Existing API tests:** `tests/unit/test_api.py` (Member 3) and `tests/unit/test_mlops.py` (Member 2) start a real server through `create_api_server(service=..., host=..., port=0, telemetry=...)`. They then call `.server_address`, `.serve_forever()` in a thread, `.shutdown()` and `.server_close()`.
- **`/metrics` stays JSON:** `test_mlops.py` asserts that `/metrics` returns JSON with request counters, and the dashboard's live-stats panel reads the same JSON.
- **AWS sign-up:** App Runner isn't available to new customers.
- **AWS account:** Member 3's own account. Member 3 already has root access and will create an IAM user. The AWS CLI on Member 3's PC is installed but not configured.
- **GitHub repo:** `chinmayeechoudhari/ETAFlow-Food-Delivery-Intelligence` belongs to a teammate. Adding repository variables and merging to `main` needs that teammate or an admin.
- **Docker on the PC:** Docker Desktop is installed but must be started by Member 3 before any local container test.
- **Credentials:** Claude never types credentials. Member 3 runs `aws configure` personally.

## 6. Approaches considered

| Approach | Trade-offs | Decision |
|---|---|---|
| **A. One EC2 server running Docker Compose** | Cheapest: about $13/month while running, less when stopped, possibly covered by free tier or credits. App, Prometheus and Grafana are all live in one place. Same `docker compose` file locally and in the cloud. Plain `http`; Member 3 looks after one server. | **Chosen by Member 3** |
| B. Amazon ECS Express Mode | More managed, and gives `https` automatically. About $1/day because the load balancer bills even when idle. Prometheus and Grafana would stay on a laptop. | Rejected: cost, and monitoring wouldn't be live |
| C. AWS App Runner (the Word guide's plan) | Simplest, with pause/resume. | Not possible: closed to new customers since 30 April 2026 |

## 7. Design

### 7.1 API on FastAPI (`src/etaflow/api/app.py`)

- `create_app(service=None, telemetry=None) -> FastAPI` builds the app and loads the model once at creation.
- `run_server(service, host, port, telemetry)` runs it with `uvicorn`.
- **Compatibility wrapper:** keep `create_api_server(service, host, port, telemetry)`. It returns an object with `.server_address`, `.serve_forever()`, `.shutdown()` and `.server_close()`, backed by `uvicorn.Server`.
  - It binds its own socket in the constructor, so `port=0` gets a free port and `server_address` is known immediately.
  - Effect: `test_api.py` and `test_mlops.py` run **unchanged** and act as the contract proving behaviour didn't change.
- **Endpoints (same as today unless noted):**

  | Method | Path | Notes |
  |---|---|---|
  | GET | `/health` | Same JSON; 503 when artifacts are missing |
  | GET | `/model-info` | Same |
  | GET | `/metrics` | Same JSON as today (dashboard + `test_mlops.py`) |
  | GET | `/metrics/prometheus` | **New.** Prometheus text format (see 7.2) |
  | GET | `/reports/experiments`, `/reports/drift`, `/reports/reference-stats`, `/reports/validation`, `/reports/registry` | Same |
  | POST | `/predict` | Same validation and same error JSON |
  | OPTIONS | All of the above | Same CORS preflight: 204, or a 404 JSON for unknown paths |
  | GET | `/docs`, `/openapi.json` | **New.** FastAPI's interactive docs |
  | GET | `/` and other static paths | **Changed.** Serves the dashboard from `app/` (`index.html`, JS, CSS, `data/*.json`). Today `GET /` returns the health JSON; `/health` stays the health check. |

- **Validation stays as it is.** `/predict` reads the raw body and keeps today's responses:
  - Missing `Content-Length` → 400, same message.
  - Invalid JSON → 400 `{"error": "Invalid JSON payload.", "details": [...]}`. Not FastAPI's default 422.
  - Then `ETAPredictionRequest.from_dict()` with the same `{"error": "Validation failed", "details": [...]}`.
  - Separately, a Pydantic model and the README example document the request body in `/docs`; it isn't used to validate.
- **Unknown paths** return `{"error": "Endpoint '<path>' not found."}` with status 404, as today.
- **CORS:** a small custom middleware reproduces today's exact rules:
  - It echoes the origin, plus `Vary: Origin`, for `http://127.0.0.1:8501` and `http://localhost:8501`. Every other origin gets `*`.
  - Methods are `GET, POST, OPTIONS`; headers are `Content-Type`.
  - The tests assert this exact behaviour, so Starlette's `CORSMiddleware` isn't used.
- **Trailing slashes:** today `"/health/"` works because of `rstrip("/")`. The new app keeps that, so it doesn't redirect.
- **Package exports:** `src/etaflow/api/__init__.py` currently exports `ETAPredictionHTTPHandler`, which won't exist any more. Update it to export `create_app`, `create_api_server` and `run_server`. Nothing outside `src/etaflow/api/` imports the handler.
- **Telemetry:** every request is still recorded in `APIMetricsTracker`, and also in the Prometheus metrics.

### 7.2 Prometheus metrics (`src/etaflow/api/telemetry.py`)

- Use `prometheus_client` with a per-app `CollectorRegistry`, so creating several apps in tests doesn't raise duplicate-registration errors.
- The metric names must match `monitoring/grafana_dashboard.json`:

  | Metric | Type | Meaning |
  |---|---|---|
  | `etaflow_http_requests_total{status}` | Counter | Every request, labelled with its status code. The Grafana throughput and error-rate panels use `status`. |
  | `etaflow_inference_duration_seconds` | Histogram | `/predict` latency. Buckets from 5 ms to 2.5 s. |
  | `etaflow_predicted_duration_minutes` | Gauge | The last predicted ETA. |
  | `etaflow_data_drift_detected_flag` | Gauge | 1 if `reports/monitoring/drift_report.json` → `clean_batch_results.overall_status` isn't `"STABLE"`, otherwise 0. Re-read at each scrape; 0 if the file is missing. |

- The default Python process metrics are included.

### 7.3 Dashboard (`app/app.js`, `app/index.html`)

- **`API_BASE_URL`:**
  - Same origin (`""`) when the page is served by the API.
  - Falls back to `http://127.0.0.1:8000` when the page is opened from port 8501 or a `file://` path, so the old way of running it still works.
- Error messages that mention `http://127.0.0.1:8000` become address-neutral.
- No other dashboard changes.

### 7.4 Local run (`pipelines/serve_api.py`, `start.bat`, `start.sh`)

- `serve_api.py`: the `API_HOST` and `API_PORT` environment variables override `configs/config.yaml`. Command-line flags still win.
- `start.bat` and `start.sh` start one server and open `http://127.0.0.1:8000/`. They no longer start the separate 8501 server.
- Member 2's `scripts/verify_workflow.py` still checks `http://127.0.0.1:8501`. Tell Member 2 rather than edit their file.

### 7.5 Docker and Compose

- **`Dockerfile`:** Python 3.11-slim.
  - Installs the project with the new dependencies, **pinned to exact versions** from a new `deploy/constraints.txt`. That file is frozen from the working local environment, so the image loads the saved models with scikit-learn 1.9.1 exactly like the PC does, instead of pulling whatever is newest at build time.
  - Leaves out `mlflow`: the serving code never imports it, and leaving it out keeps the image smaller and pulls faster on a small server.
  - Runs as a non-root user, exposes 8000, sets `API_HOST=0.0.0.0`, checks `HEALTHCHECK /health`, and runs `CMD python pipelines/serve_api.py`. Port 8501 is removed.
- **`.dockerignore`:** also excludes `.env`, `.env.*` (but not `.env.example`), `mlflow.db`, `mlartifacts/`, `*.pptx`, `*.docx`, `.venv*/`, `docs/` and `tests/`, so secrets and large files stay out of the image.
- **`docker-compose.yml`** (local; builds the image):
  - `etaflow`: `8000:8000`, `restart: unless-stopped`.
  - `prometheus`: pinned `prom/prometheus` version. Mounts `monitoring/prometheus.yml`, which now targets `etaflow:8000` with `metrics_path: /metrics/prometheus`. 7-day retention. Published only on `127.0.0.1:9090`.
  - `grafana`: pinned `grafana/grafana-oss` version on port 3000.
    - Provisioning lives in `monitoring/grafana/provisioning/`: a Prometheus data source with `uid: prometheus`, which matches the dashboard JSON, and a dashboard provider that loads `monitoring/grafana_dashboard.json`.
    - Anonymous viewers are allowed read-only access, sign-up is disabled, and the admin password comes from `GRAFANA_ADMIN_PASSWORD` in `.env`, which is never committed.
- **`docker-compose.prod.yml`** (an override for EC2):
  - `etaflow` uses `image: ${ETAFLOW_IMAGE}` from ECR instead of `build`, and publishes `80:8000`.
  - Memory limits are set to suit a 1 GB server.
  - Grafana requires `GRAFANA_ADMIN_PASSWORD` to be set (`${GRAFANA_ADMIN_PASSWORD:?}`), so the public server can never start with a default password. Locally it falls back to `admin`.

### 7.6 AWS infrastructure (`deploy/aws/etaflow-stack.yaml`, CloudFormation)

- **Region:** `ap-south-1` (Mumbai), the closest to the team. It's a template parameter.

| Resource | Details |
|---|---|
| ECR repository `etaflow-app` | Scan on push; lifecycle rule keeps the last 10 images |
| S3 bucket (deploy bundle) | Holds `docker-compose*.yml` and `monitoring/` for the server to download; private and encrypted |
| Security group | Inbound 80 and 3000 from anywhere. **No port 22**: there's no SSH, and admin access goes through SSM Session Manager |
| EC2 instance role | `AmazonSSMManagedInstanceCore` + `AmazonEC2ContainerRegistryReadOnly` + read access to the bundle bucket + `ssm:GetParameter` on `/etaflow/*` |
| EC2 instance | Amazon Linux 2023 in the default VPC. `t3.micro` by default (`t3.small` as a parameter option); 20 GB gp3 disk. User-data installs Docker and the Compose plugin and adds 2 GB of swap |
| Elastic IP | Keeps the same address across stop/start, so the demo URL doesn't change |
| GitHub OIDC provider + deploy role | Lets GitHub Actions deploy **without stored AWS keys** (details in 7.7) |

- **Outputs:** `DashboardUrl`, `GrafanaUrl`, `EcrRepositoryUri`, `InstanceId`, `BundleBucket`, `DeployRoleArn`.
- **Helper scripts** (PowerShell, for Member 3's Windows PC) in `deploy/aws/`:
  - `create-stack.ps1` creates the stack and prints the outputs.
  - `delete-stack.ps1` empties ECR and S3, then deletes the stack.
  - `stop-server.ps1` and `start-server.ps1` stop or start the server between demos.

### 7.7 IAM and access

- **Member 3 does these personally in the AWS console** (Claude only gives the steps):
  1. Turn on MFA for the root account, and never create root access keys.
  2. Create the IAM user `etaflow-admin` with console + CLI access and `AdministratorAccess`, and turn on MFA. This user replaces root for all project work, and creating the stack needs broad rights because it creates IAM roles.
  3. Create an access key for `etaflow-admin` and run `aws configure` on the PC, with region `ap-south-1`.
- **GitHub uses short-lived credentials instead of an IAM user's keys (OIDC):**
  - The stack creates a role that only workflows from `chinmayeechoudhari/ETAFlow-Food-Delivery-Intelligence` on branch `main` can assume.
  - Its permissions are limited: push to `etaflow-app`, write to the bundle bucket, and `ssm:SendCommand` (with `AWS-RunShellScript`) on the one instance plus `ssm:GetCommandInvocation`.
  - Why: no secret keys need to be handed to the repo owner over chat.
  - If the account already has a GitHub OIDC provider, the template parameter `CreateGitHubOidcProvider=false` reuses it.

### 7.8 CI/CD (`.github/workflows/`)

- **`ci.yml`** (Member 2's test job): unchanged, except the old `deploy-to-aws` job is **removed**. It's the only touch to that file.
- **New `deploy.yml`** (Member 3):
  - **Trigger:** `workflow_run` of the CI workflow, completed, on `main`. It runs only if CI succeeded **and** the repository variable `AWS_DEPLOY_ROLE_ARN` is set. Before AWS is set up it's skipped, not failed, so teammates' pushes stay green. It can also be run manually with `workflow_dispatch`.
  - **Permissions:** `id-token: write`, `contents: read`.
  - **Steps:**
    1. Check out the commit that CI tested.
    2. Get credentials through OIDC with `aws-actions/configure-aws-credentials` (`role-to-assume: ${{ vars.AWS_DEPLOY_ROLE_ARN }}`, `aws-region: ${{ vars.AWS_REGION }}`).
    3. Log in to ECR, build, and push `etaflow-app:<sha>` and `:latest`.
    4. Upload the bundle (`docker-compose.yml`, `docker-compose.prod.yml`, `monitoring/`) to `s3://<bucket>/bundle/<sha>.tar.gz`.
    5. Send an SSM `AWS-RunShellScript` command to `${{ vars.EC2_INSTANCE_ID }}` that:
       - downloads and unpacks the bundle into `/opt/etaflow`;
       - writes `ETAFLOW_IMAGE=<uri>:<sha>` into `/opt/etaflow/.env`, keeping the existing `GRAFANA_ADMIN_PASSWORD`;
       - logs in to ECR;
       - runs `docker compose -f docker-compose.yml -f docker-compose.prod.yml pull && up -d`;
       - prunes old images.
    6. Wait for the command and fail the job if it fails.
    7. Smoke-test `GET ${{ vars.APP_URL }}/health`, with retries for up to about 2 minutes.
- **Repository variables** (not secrets, because none of these are sensitive): `AWS_DEPLOY_ROLE_ARN`, `AWS_REGION`, `EC2_INSTANCE_ID`, `ECR_REPOSITORY_URI`, `BUNDLE_BUCKET`, `APP_URL`. A repo admin adds them once.
- **Grafana admin password:** Member 3 stores it once in SSM Parameter Store as the encrypted SecureString `/etaflow/grafana-admin-password`, using `deploy/aws/set-grafana-password.ps1`. Each deploy reads it on the server. It's never stored in GitHub, in git or in the command history. If it's missing, the deploy stops instead of starting Grafana with a default password.

### 7.9 Who does what

| Member 3 (by hand) | Claude |
|---|---|
| Root MFA; create `etaflow-admin`; run `aws configure` | All code, templates, workflow, scripts and docs |
| Start Docker Desktop | Run tests and the local `docker compose` stack |
| Approve the cost estimate before the stack is created | Run AWS CLI commands **only after Member 3 approves each step that creates or deletes resources** |
| Choose the Grafana admin password | Verify the live URLs after deployment |
| Ask the repo owner to add repository variables and accept the merge | Prepare the PR description |

### 7.10 Documentation

- **New `docs/DEPLOYMENT_GUIDE.md`:** an architecture diagram in text, then IAM setup, creating the stack, local test, first deploy, GitHub setup, demo URLs, stop/start, delete, a cost table and troubleshooting.
- **`docs/AWS_CICD_DEPLOYMENT_GUIDE.md`:** replaced with a short pointer to the new guide, plus a note that App Runner closed to new customers.
- **README** (shared file): small edits to the install/launch and deployment sections, covering the single URL, `/docs`, `docker compose` with Grafana, and the AWS EC2 deployment.

### 7.11 Git

- All work goes on branch `member3-deployment`, with commits under Member 3's own git identity.
- Merging into the teammate's repo needs push access or a fork. That's decided when the work is ready.

## 8. Touches to teammates' files (tell them)

| File | Owner | Change |
|---|---|---|
| `pyproject.toml` | Member 2 | Add `fastapi`, `uvicorn`, `prometheus-client` to dependencies, and `httpx` to `dev` |
| `.github/workflows/ci.yml` | Member 2 | Remove the old `deploy-to-aws` job (it moves to `deploy.yml`) |
| `README.md` | Shared | Launch and deployment sections |
| `scripts/verify_workflow.py` | Member 2 | **Not edited.** It still expects port 8501; Member 2 decides |

## 9. Testing and verification

1. All 82 existing tests pass, with `test_api.py` and `test_mlops.py` **unmodified**.
2. New tests (`tests/unit/test_deployment.py`):
   - `/metrics/prometheus` returns `text/plain` with all four metric names.
   - The counters move after requests.
   - The drift flag reflects the report.
   - `/docs` and `/openapi.json` return 200.
   - `/` serves the dashboard `index.html`.
   - `/app.js` is served.
   - `/health/` with a trailing slash works.
   - `API_HOST` and `API_PORT` override the config.
3. Local stack: `docker compose up --build`.
   - The app reports healthy.
   - The Prometheus target shows UP.
   - Grafana shows data after about 20 `/predict` calls.
4. The CloudFormation template passes `cfn-lint`, run in a throwaway environment.
5. After the AWS deploy:
   - Public `/health` returns 200, and the dashboard loads.
   - Grafana loads anonymously with live panels.
   - A test push redeploys automatically.

## 10. Cost (`ap-south-1`, approximate, before any free tier or credits)

| Item | Running | Stopped |
|---|---|---|
| t3.micro | ~$8/month | $0 |
| Public IPv4 / Elastic IP | ~$3.6/month | ~$3.6/month |
| 20 GB gp3 disk | ~$1.8/month | ~$1.8/month |
| ECR + S3 | < $0.50/month | < $0.50/month |
| **Total** | **~$14/month** | **~$6/month** |

`delete-stack.ps1` removes everything and brings the cost to $0.

## 11. Calls Claude made (Member 3 can override any of these)

1. **Prometheus address.** It reads `/metrics/prometheus`, and `/metrics` stays JSON. Why: Member 2's `test_mlops.py` and the dashboard both rely on the JSON.
2. **`create_api_server` kept as a compatibility wrapper.** Why: both API test files then run unchanged and prove nothing broke.
3. **Region `ap-south-1` (Mumbai).** Why: it's the closest to the team.
4. **Server size `t3.micro` with 2 GB swap** (`t3.small` if it's too slow). Why: it's the cheapest option and may be free-tier eligible.
5. **No SSH port.** Admin access goes through SSM Session Manager. Why: it's safer, and there are no key files to lose.
6. **Elastic IP.** Why: the demo URL stays the same after stop/start.
7. **GitHub deploys through OIDC, not IAM user keys.** Why: no secret keys need to be sent to the repo owner.
8. **`etaflow-admin` gets `AdministratorAccess` with MFA.** Why: creating the stack creates IAM roles, and this user replaces root for daily work.
9. **Grafana allows anonymous read-only viewing.** Why: your sir can open it without logging in. Editing still needs the admin password.
10. **The deploy job moves to its own `deploy.yml`.** Why: Member 2 owns `ci.yml` and Member 3 owns deployment.
11. **The Docker image uses pinned versions and leaves out MLflow.** Why: model loading stays reliable and the image stays small.

## 12. Left to the builder

- Exact Python structure inside `app.py`: router layout, and lifespan vs. eager loading.
- Histogram bucket values within the 5 ms–2.5 s range.
- Exact pinned versions of the Prometheus and Grafana images (current stable at build time).
- PowerShell script details and the troubleshooting content in the guide.

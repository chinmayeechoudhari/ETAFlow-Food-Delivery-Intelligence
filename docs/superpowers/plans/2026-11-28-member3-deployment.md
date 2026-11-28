# ETAFlow Member 3 Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put ETAFlow online in Member 3's AWS account as a FastAPI app that also serves the dashboard, with live Prometheus + Grafana monitoring, created from one CloudFormation template and redeployed automatically on every push to `main`.

**Architecture:** `src/etaflow/api/app.py` becomes a FastAPI app. It serves the existing API routes, a new Prometheus endpoint, `/docs`, and the static dashboard from `app/`, all on one port. A compatibility wrapper keeps the existing test harness working unchanged. Docker Compose runs the app, Prometheus and Grafana together. Locally it builds the image; on EC2 a prod override pulls the image from ECR. A GitHub Actions workflow assumes an AWS role through OIDC, pushes the image and a config bundle, and tells the EC2 server through SSM to run `deploy/remote-deploy.sh`.

**Tech Stack:** Python 3.11, FastAPI 0.162.2, uvicorn 0.54.0, prometheus-client 0.26.0, httpx 0.28.1 (tests only), Docker Compose v2.24+, Prometheus, Grafana OSS, AWS CloudFormation, EC2 (Amazon Linux 2023), ECR, S3, SSM, GitHub Actions OIDC, and PowerShell scripts for the Windows PC.

**Spec:** `docs/superpowers/specs/2026-11-23-member3-deployment-design.md`

## Global Constraints

- **Branch:** all commits go on `member3-deployment` under the local git identity. Never push or merge without Member 3 asking.
- **Unchanged contract tests:** `tests/unit/test_api.py` and `tests/unit/test_mlops.py` must pass **unmodified**. They are the contract that behaviour didn't change.
- **Ownership:** teammates' files are touched only as follows:
  - `pyproject.toml`: add dependencies only.
  - `.github/workflows/ci.yml`: delete the `deploy-to-aws` job only.
  - `README.md`: launch and deployment sections only.
- **Pinned versions:** the image installs with `-c deploy/constraints.txt`, which includes `scikit-learn==1.9.1`, `numpy==2.4.6` and `pandas==3.1.1`. `mlflow` is not installed in the image.
- **Metric names**, exactly: `etaflow_http_requests_total` (label `status`), `etaflow_inference_duration_seconds` (histogram), `etaflow_predicted_duration_minutes` (gauge), `etaflow_data_drift_detected_flag` (gauge).
- **Endpoints:**
  - `/metrics` keeps returning today's JSON.
  - Prometheus scrapes `/metrics/prometheus`.
  - Grafana data source uid is `prometheus`; dashboard uid is `etaflow-prod-overview`.
- **AWS identifiers:**
  - Region default `ap-south-1`; stack name default `etaflow`; ECR repository `etaflow-app`.
  - GitHub repo `chinmayeechoudhari/ETAFlow-Food-Delivery-Intelligence`, branch `main`.
  - SSM parameter `/etaflow/grafana-admin-password` (SecureString).
- **Security rules:**
  - No inbound port 22. No AWS keys, passwords or `.env` files in git or in the image.
  - Container images are pinned to exact tags, never `latest`. (The ECR app image's own `:latest` tag is fine.)
- **User gates:** Claude never types credentials, and runs AWS commands that create, change or delete resources only after Member 3 approves that step in chat.
- **Test command:** `$env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m pytest -q` from the repo root. Lint: `.\.venv\Scripts\ruff.exe check src pipelines tests`.

## Review Focus

1. **Many `/predict` calls at once.** The What-If Lab fires bursts. Every request must succeed, and the counters must be exact. → Task 3, `test_concurrent_predictions_all_succeed`.
2. **Non-UTF-8 or truncated body to `/predict`.** It must give a 400 JSON error, never a 500 or a hang. → Task 3, `test_non_utf8_body_returns_400`.
3. **Drift report missing or corrupt on the server.** `/metrics/prometheus` must still return 200, with the drift flag at 0. → Task 2, `test_drift_flag_missing_or_corrupt_report`.
4. **Path traversal through the static dashboard mount** (`/../configs/config.yaml`). It must return 404 and leak no file. → Task 3, `test_static_path_traversal_blocked`.
5. **Prod stack started without a Grafana password.** It must refuse to start, never fall back to `admin`. → Task 7, compose-config check and `remote-deploy.sh` guard.

---

## File map

| File | Status | Responsibility |
|---|---|---|
| `deploy/constraints.txt` | Create | Exact versions frozen from the working `.venv` |
| `pyproject.toml` | Modify (M2) | Add `fastapi`, `uvicorn`, `prometheus-client`; `httpx` in `dev` |
| `src/etaflow/api/telemetry.py` | Modify | Add `PrometheusMetrics` next to `APIMetricsTracker` |
| `src/etaflow/api/app.py` | Rewrite | `create_app`, `ServerHandle`, `create_api_server`, `run_server` |
| `src/etaflow/api/settings.py` | Create | `resolve_bind_address` (CLI > env > config > default) |
| `src/etaflow/api/__init__.py` | Modify | Export the new names; drop `ETAPredictionHTTPHandler` |
| `pipelines/serve_api.py` | Modify | Use `resolve_bind_address` with `os.environ` |
| `tests/unit/test_deployment.py` | Create | All new tests |
| `app/app.js` | Modify | Same-origin API base and address-neutral error text |
| `start.bat`, `start.sh` | Modify | One server; open `http://127.0.0.1:8000/` |
| `Dockerfile`, `.dockerignore` | Modify | Pinned, non-root, binds `0.0.0.0`; secrets and large files kept out |
| `docker-compose.yml` | Rewrite | Local stack: etaflow + prometheus + grafana |
| `docker-compose.prod.yml` | Create | EC2 override: ECR image, port 80, memory limits, required password |
| `monitoring/prometheus.yml` | Modify | Target `etaflow:8000`, `metrics_path: /metrics/prometheus` |
| `monitoring/grafana/provisioning/datasources/prometheus.yml` | Create | Data source uid `prometheus` |
| `monitoring/grafana/provisioning/dashboards/etaflow.yml` | Create | Loads `/var/lib/grafana/dashboards/grafana_dashboard.json` |
| `.env.example` | Modify | Add `GRAFANA_ADMIN_PASSWORD=` placeholder |
| `deploy/aws/etaflow-stack.yaml` | Create | CloudFormation for every AWS resource |
| `deploy/remote-deploy.sh` | Create | Runs on EC2: login, write `.env`, `compose pull/up` |
| `deploy/aws/*.ps1` | Create | create / delete / deploy-now / set-grafana-password / stop / start |
| `.github/workflows/deploy.yml` | Create | OIDC deploy after CI succeeds |
| `.github/workflows/ci.yml` | Modify (M2) | Remove the `deploy-to-aws` job |
| `docs/DEPLOYMENT_GUIDE.md` | Create | End-to-end guide |
| `docs/AWS_CICD_DEPLOYMENT_GUIDE.md`, `README.md` | Modify | Point at the new guide; correct launch steps |

---

### Task 1: Pin serving dependencies

**Files:**
- Create: `deploy/constraints.txt`
- Modify: `pyproject.toml` (`[project].dependencies`, `[project.optional-dependencies].dev`)

**Interfaces:**
- Produces: `deploy/constraints.txt`, consumed by the Dockerfile (Task 6) as `pip install -c deploy/constraints.txt -e .`.

- [ ] **Step 1: Freeze the working environment**

  Run: `uv pip freeze --python .venv/Scripts/python.exe --exclude-editable > deploy/constraints.txt`

  Then add a two-line `#` header saying the file is generated from the working `.venv` and pins `scikit-learn 1.9.1` for the saved models.

  Expected: the file contains `scikit-learn==1.9.1`, `fastapi==0.162.2`, `uvicorn==0.54.0` and `prometheus-client==0.26.0`.

- [ ] **Step 2: Add dependencies to `pyproject.toml`**

  - `dependencies` gains `fastapi>=0.100.0`, `uvicorn>=0.22.0` and `prometheus-client>=0.19.0` (the floors from `requirements.txt`).
  - `dev` gains `httpx>=0.27.0`.

- [ ] **Step 3: Verify that resolution under the constraints works**

  Run: `uv pip install --python .venv/Scripts/python.exe --dry-run -e ".[dev]" -c deploy/constraints.txt`

  Expected: `Would make no changes`, or only the editable reinstall of `etaflow`. No version changes.

- [ ] **Step 4: Commit**

  `git add deploy/constraints.txt pyproject.toml && git commit -m "build(deploy): pin serving dependencies for the container image"`

---

### Task 2: Prometheus metrics collector

**Files:**
- Modify: `src/etaflow/api/telemetry.py`
- Test: `tests/unit/test_deployment.py` (create; class `TestPrometheusMetrics`)

**Interfaces:**
- Produces, in `etaflow.api.telemetry`:
  - `class PrometheusMetrics`
  - `__init__(self, drift_report_path: Optional[Path] = None) -> None`
  - `record_request(self, status_code: int) -> None`
  - `record_prediction(self, latency_seconds: float, predicted_minutes: float) -> None`
  - `render(self) -> Tuple[bytes, str]`, which returns `(body, content_type)`
  - `DEFAULT_DRIFT_REPORT_PATH: Path` (`<repo>/reports/monitoring/drift_report.json`)

- [ ] **Step 1: Write the failing tests**

  ```python
  class TestPrometheusMetrics(unittest.TestCase):
      def _write_report(self, tmp: Path, status: str) -> Path:
          p = tmp / "drift_report.json"
          p.write_text(json.dumps({"clean_batch_results": {"overall_status": status}}), encoding="utf-8")
          return p

      def test_render_contains_all_grafana_metrics(self):
          m = PrometheusMetrics(drift_report_path=Path("missing.json"))
          m.record_request(200)
          m.record_prediction(latency_seconds=0.012, predicted_minutes=20.29)
          body, ctype = m.render()
          text = body.decode()
          self.assertTrue(ctype.startswith("text/plain"))
          self.assertIn('etaflow_http_requests_total{status="200"} 1.0', text)
          self.assertIn("etaflow_inference_duration_seconds_count 1.0", text)
          self.assertIn("etaflow_predicted_duration_minutes 20.29", text)
          self.assertIn("etaflow_data_drift_detected_flag 0.0", text)

      def test_drift_flag_follows_report(self):
          with tempfile.TemporaryDirectory() as d:
              stable = PrometheusMetrics(self._write_report(Path(d), "STABLE")).render()[0].decode()
              self.assertIn("etaflow_data_drift_detected_flag 0.0", stable)
              drift = PrometheusMetrics(self._write_report(Path(d), "DRIFT_DETECTED")).render()[0].decode()
              self.assertIn("etaflow_data_drift_detected_flag 1.0", drift)

      def test_drift_flag_missing_or_corrupt_report(self):
          with tempfile.TemporaryDirectory() as d:
              bad = Path(d) / "drift_report.json"
              bad.write_text("{not json", encoding="utf-8")
              for path in (bad, Path(d) / "absent.json"):
                  text = PrometheusMetrics(path).render()[0].decode()
                  self.assertIn("etaflow_data_drift_detected_flag 0.0", text)

      def test_two_instances_do_not_collide(self):
          PrometheusMetrics(); PrometheusMetrics()  # must not raise duplicate-registration errors
  ```

- [ ] **Step 2: Run the tests and verify they fail**

  Run: `pytest tests/unit/test_deployment.py -k Prometheus -v`

  Expected: FAIL with `ImportError: cannot import name 'PrometheusMetrics'`.

- [ ] **Step 3: Implement `PrometheusMetrics` in `telemetry.py`**

  - Each instance owns a `prometheus_client.CollectorRegistry`, which also gets `ProcessCollector` and `PlatformCollector`.
  - Histogram buckets: `(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5)`.
  - The drift flag is a custom collector. At each scrape it reads `drift_report_path` and yields `GaugeMetricFamily` with value `1.0` when `clean_batch_results.overall_status != "STABLE"`, and `0.0` on any read or parse error or a missing key.
  - `render()` returns `generate_latest(registry), CONTENT_TYPE_LATEST`.

- [ ] **Step 4: Run the tests and verify they pass**

  Run: `pytest tests/unit/test_deployment.py -k Prometheus -v`

  Expected: 4 passed.

- [ ] **Step 5: Commit**

  `git commit -m "feat(api): add Prometheus metrics matching the Grafana dashboard"`, with the two files.

---

### Task 3: FastAPI app with compatibility wrapper

**Files:**
- Rewrite: `src/etaflow/api/app.py` (reference for behaviour: `git show main:src/etaflow/api/app.py`)
- Modify: `src/etaflow/api/__init__.py`
- Test: `tests/unit/test_deployment.py` (class `TestFastAPIApp`); `tests/unit/test_api.py` and `tests/unit/test_mlops.py` unchanged

**Interfaces:**
- Consumes: `PrometheusMetrics` (Task 2); `APIMetricsTracker.record_request(status_code, latency_ms=None, is_predict=False)`; `ETAPredictionRequest.from_dict(dict) -> (request|None, errors: list)`; `ETAPredictionService.is_ready`, `.model_identity`, `.get_model_info()`, `.predict(request) -> ETAPredictionResponse` (`.to_dict()`, `.predicted_duration_minutes`); `ArtifactUnavailableError`.
- Produces, in `etaflow.api.app`:
  - `PROJECT_ROOT: Path`, `API_PATHS: frozenset[str]`
  - `create_app(service: Optional[ETAPredictionService] = None, telemetry: Optional[APIMetricsTracker] = None, metrics: Optional[PrometheusMetrics] = None, static_dir: Optional[Path] = None) -> FastAPI`
  - `class ServerHandle` with `server_address: Tuple[str, int]`, `serve_forever() -> None`, `shutdown() -> None`, `server_close() -> None`
  - `create_api_server(service=None, host="127.0.0.1", port=8000, telemetry=None) -> ServerHandle`
  - `run_server(service=None, host="127.0.0.1", port=8000, telemetry=None) -> None`
  - `etaflow.api.__init__` exports `create_app`, `create_api_server` and `run_server` in place of `ETAPredictionHTTPHandler`.

- [ ] **Step 1: Write the failing tests**

  Use `fastapi.testclient.TestClient(create_app(service=ETAPredictionService()))` (class-level fixture), except where a real server is noted. `VALID` is the README `/predict` example payload.

  - `test_docs_and_openapi_available`:
    - `GET /docs` → 200 and `"text/html"` in the content type.
    - `GET /openapi.json` → 200 and `"/predict" in body["paths"]`.
  - `test_root_serves_dashboard`: `GET /` → 200, with `"Dispatch Control Center"` in the text.
  - `test_static_asset_served`: `GET /app.js` → 200, with `"API_BASE_URL"` in the text.
  - `test_prometheus_endpoint_counts_predictions` (uses its own fresh `create_app` instance so earlier tests can't change the count):
    - `POST /predict` with `VALID` → 200.
    - Then `GET /metrics/prometheus` → 200, content type starts with `text/plain`, and the body contains `etaflow_inference_duration_seconds_count 1.0` and `status="200"`.
  - `test_metrics_json_unchanged`: `GET /metrics` → JSON containing keys `latency_ms` and `total_requests`.
  - `test_trailing_slash_not_redirected`: `GET /health/` with `follow_redirects=False` → 200 and `status == "healthy"`.
  - `test_unknown_path_json_404`: `GET /nope` → 404 and `{"error": "Endpoint '/nope' not found."}`.
  - `test_non_utf8_body_returns_400`: `POST /predict` with `content=b"\xff\xfe\x00"` and header `Content-Type: application/json` → 400 with `"error"` in the JSON.
  - `test_static_path_traversal_blocked`: for each of `"/../configs/config.yaml"`, `"/..%2fconfigs%2fconfig.yaml"` and `"/%2e%2e/configs/config.yaml"`, the status is 404 and `"model_name"` isn't in the text.
  - `test_concurrent_predictions_all_succeed`, using a **real server** via `create_api_server(port=0)` in a thread:
    - Read the `/metrics` JSON `successful_predictions` first.
    - Fire 20 `POST /predict` with `VALID` through `ThreadPoolExecutor(max_workers=10)` and `urllib`.
    - All return 200, and `successful_predictions` rose by exactly 20.
    - Then call `shutdown()`.
  - `test_server_handle_lifecycle`:
    - `h = create_api_server(port=0)`, and `h.server_address[1] > 0` before serving.
    - Serve in a thread; `/health` → 200.
    - `h.shutdown()`; the thread joins within 5 s; then `h.server_close()`.

- [ ] **Step 2: Run the new tests and verify they fail**

  Run: `pytest tests/unit/test_deployment.py -k FastAPI -v`

  Expected: FAIL with `ImportError: cannot import name 'create_app'`.

- [ ] **Step 3: Implement `create_app` in `app.py`**

  - **Routes.** Port each branch of the old `do_GET`, `do_POST` and `do_OPTIONS` one-to-one: the same status codes, JSON bodies, `REPORT_ENDPOINTS` map and telemetry calls.
  - **Recording helper.** All recording goes through one helper. It calls `telemetry.record_request(...)` and `metrics.record_request(status)`; a successful predict also calls `metrics.record_prediction(latency_s, response.predicted_duration_minutes)`.
  - **`/predict`:**
    - `async`. Reads `await request.body()`.
    - Missing or empty body: 400 with `"Missing Content-Length header or empty body."`.
    - Decode or `json` errors: 400 `{"error": "Invalid JSON payload.", "details": [str(exc)]}`.
    - A non-dict JSON payload goes through the same 400 path as `from_dict` errors.
    - Runs `service.predict` through `starlette.concurrency.run_in_threadpool`.
  - **`GET /metrics/prometheus`** returns `Response(body, media_type=content_type)` and records the request like the other GETs.
  - **Path middleware (pure ASGI).** Strips one trailing `/` from `scope["path"]` when the path isn't `/`. Built with `FastAPI(redirect_slashes=False)`.
  - **CORS middleware (pure ASGI, outermost).**
    - `OPTIONS` to a path in `API_PATHS`: 204 with CORS headers and `Content-Length: 0`.
    - `OPTIONS` to any other path: 404 JSON with CORS headers. No telemetry for `OPTIONS`, as before.
    - Every other response gets the same CORS headers as the old `_send_cors_headers`: echo the origin plus `Vary: Origin` for the two `:8501` origins, else `*`. Methods `GET, POST, OPTIONS`; headers `Content-Type`.
  - **Static files.** `app.mount("/", StaticFiles(directory=static_dir, html=True))` after all routes, skipped if `static_dir` doesn't exist. A `StarletteHTTPException` handler turns 404s into `{"error": f"Endpoint '{request.url.path}' not found."}` and records them like the old unknown-path branch. Successful static responses aren't recorded.
  - **Docs body.** `/predict` documents its body with `openapi_extra` built from a Pydantic model `PredictRequestDoc`: the ten README fields, with the README example. It's for docs only; validation stays with `from_dict`.
  - **App settings.** `title="ETAFlow Prediction API"`, `version=etaflow.__version__`.

- [ ] **Step 4: Implement `ServerHandle`, `create_api_server` and `run_server`**

  - **`ServerHandle.__init__`:**
    - Binds `socket.socket(AF_INET, SOCK_STREAM)` to `(host, port)`, without `SO_REUSEADDR`, and sets it listening.
    - Stores `server_address = sock.getsockname()`.
    - Builds `uvicorn.Server(uvicorn.Config(app, log_level="warning", lifespan="off"))`.
  - **`serve_forever()`** runs `server.run(sockets=[sock])` and sets a `threading.Event` on return.
  - **`shutdown()`** sets `server.should_exit = True` and waits on the event for at most 10 s.
  - **`server_close()`** closes the socket.
  - **`run_server`** prints the endpoint list as before plus `/docs` and `/metrics/prometheus`, then calls `uvicorn.run(create_app(...), host=host, port=port)`.

- [ ] **Step 5: Update `src/etaflow/api/__init__.py` exports**

- [ ] **Step 6: Run all API tests and verify they pass**

  Run: `pytest tests/unit/test_deployment.py tests/unit/test_api.py tests/unit/test_mlops.py -v`

  Expected: all pass, with `test_api.py` and `test_mlops.py` unmodified (`git diff --stat main -- tests/unit/test_api.py tests/unit/test_mlops.py` prints nothing).

- [ ] **Step 7: Run the full suite and lint**

  Expected: everything passes (82 existing + the new tests); `ruff check` is clean.

- [ ] **Step 8: Commit**

  `git commit -m "feat(api): serve API and dashboard with FastAPI, add /docs and /metrics/prometheus"`

---

### Task 4: Bind address from the environment

**Files:**
- Create: `src/etaflow/api/settings.py`
- Modify: `pipelines/serve_api.py:24-47`
- Test: `tests/unit/test_deployment.py` (class `TestBindAddress`)

**Interfaces:**
- Produces: `resolve_bind_address(cli_host: Optional[str], cli_port: Optional[int], config_api: Mapping[str, Any], environ: Mapping[str, str]) -> Tuple[str, int]`.
  - Precedence: CLI > `API_HOST`/`API_PORT` > `config_api["host"/"port"]` > `("127.0.0.1", 8000)`.
  - A non-integer `API_PORT` raises `ValueError("API_PORT must be an integer, got 'abc'")`.

- [ ] **Step 1: Write the failing tests**

  ```python
  def test_defaults(self):
      self.assertEqual(resolve_bind_address(None, None, {}, {}), ("127.0.0.1", 8000))
  def test_config_used(self):
      self.assertEqual(resolve_bind_address(None, None, {"host": "127.0.0.1", "port": 9000}, {}), ("127.0.0.1", 9000))
  def test_env_overrides_config(self):
      self.assertEqual(resolve_bind_address(None, None, {"host": "127.0.0.1", "port": 9000},
                                            {"API_HOST": "0.0.0.0", "API_PORT": "8000"}), ("0.0.0.0", 8000))
  def test_cli_overrides_env(self):
      self.assertEqual(resolve_bind_address("127.0.0.2", 7000, {}, {"API_HOST": "0.0.0.0", "API_PORT": "8000"}), ("127.0.0.2", 7000))
  def test_bad_env_port(self):
      with self.assertRaisesRegex(ValueError, "API_PORT must be an integer, got 'abc'"):
          resolve_bind_address(None, None, {}, {"API_PORT": "abc"})
  ```

- [ ] **Step 2: Run the tests and verify they fail** (ImportError)

- [ ] **Step 3: Implement `resolve_bind_address`, and use it in `serve_api.py` with `dict(os.environ)`**

  Keep the existing config-reading and warning behaviour.

- [ ] **Step 4: Run the tests and verify they pass**

  Also run `$env:API_PORT="8123"; .\.venv\Scripts\python.exe pipelines\serve_api.py` in the background, then check that `curl http://127.0.0.1:8123/health` returns `"healthy"`. Stop the server and clear the variable.

- [ ] **Step 5: Commit**

  `git commit -m "fix(api): honour API_HOST/API_PORT so the container is reachable"`

---

### Task 5: Dashboard on one address

**Files:**
- Modify: `app/app.js:13` (the `API_BASE_URL` definition), and the two error strings at `app/app.js:990` and `app/app.js:2065`
- Modify: `start.bat`, `start.sh`

**Interfaces:**
- Produces: `function resolveApiBaseUrl(loc)` in `app.js`. It returns `"http://127.0.0.1:8000"` when `loc.protocol === "file:"` or `loc.port === "8501"`, else `""`. `const API_BASE_URL = resolveApiBaseUrl(window.location);`

- [ ] **Step 1: Implement `resolveApiBaseUrl` and the error text**

  - Error text for line 990: `"Unable to reach the ETAFlow prediction server. Start it with start.bat or 'python pipelines/serve_api.py'."`
  - Line 2065 gets the same wording, after its existing first sentence.

- [ ] **Step 2: Rewrite `start.bat` and `start.sh`**

  - Keep the `.venv` detection, `PYTHONPATH` and `.env` copy.
  - Start a 3-second delayed browser open of `http://127.0.0.1:8000/`.
  - Run `serve_api.py` in the foreground.
  - The `http.server 8501` line is removed.

- [ ] **Step 3: Verify in the browser**

  - Start `serve_api.py` in the background.
  - In the browser pane, open `http://127.0.0.1:8000/`: the dashboard loads, the Live ETA prediction for the default order returns a number, and `read_console_messages(onlyErrors)` shows no API errors.
  - Then start `python -m http.server 8501 --directory app` and open `http://127.0.0.1:8501/`: a prediction still works through the `127.0.0.1:8000` fallback.
  - Stop both servers.

- [ ] **Step 4: Run the full test suite** (all pass)

- [ ] **Step 5: Commit**

  `git commit -m "feat(dashboard): call the API on the same origin; single-server launchers"`

---

### Task 6: Local container stack (app + Prometheus + Grafana)

**Prerequisite:** Member 3 has started Docker Desktop. Check with `docker info` before Step 4.

**Files:**
- Modify: `Dockerfile`, `.dockerignore`, `monitoring/prometheus.yml`, `.env.example`
- Rewrite: `docker-compose.yml`
- Create: `monitoring/grafana/provisioning/datasources/prometheus.yml`, `monitoring/grafana/provisioning/dashboards/etaflow.yml`

**Interfaces:**
- Consumes: `deploy/constraints.txt` (Task 1); `/metrics/prometheus` and `API_HOST`/`API_PORT` (Tasks 3–4).
- Produces: compose services named `etaflow`, `prometheus` and `grafana`. Task 7 overrides `etaflow` by name, and the Grafana dashboard JSON is mounted at `/var/lib/grafana/dashboards/grafana_dashboard.json`.

- [ ] **Step 1: Dockerfile**

  - Base `python:3.11-slim`; environment `PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app/src API_HOST=0.0.0.0 API_PORT=8000`.
  - `COPY . .`, then `pip install --no-cache-dir -c deploy/constraints.txt -e .`.
  - Create user `etaflow` (uid 10001), `chown /app`, `USER etaflow`.
  - `EXPOSE 8000`.
  - `HEALTHCHECK` uses `python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=3).status==200 else 1)"`. That removes the `apt-get curl` layer.
  - `CMD ["python", "pipelines/serve_api.py"]`.

- [ ] **Step 2: `.dockerignore`**

  - Append `.env`, `.env.*`, `!.env.example`, `mlflow.db`, `mlartifacts/`, `*.pptx`, `*.docx`, `.venv*/`, `docs/`, `tests/`, `deploy/aws/` and `.github/`.
  - Keep `models/`, `reports/`, `app/`, `configs/` and `data/`.

- [ ] **Step 3: Compose, Prometheus and Grafana configuration**

  - **`etaflow` service:** `build: .`, `ports: ["8000:8000"]`, `restart: unless-stopped`.
  - **`prometheus` service:**
    - Pinned image `prom/prometheus:<current v3.x>`.
    - Mounts `./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro`.
    - Arguments `--config.file=/etc/prometheus/prometheus.yml --storage.tsdb.retention.time=7d`.
    - `ports: ["127.0.0.1:9090:9090"]`.
  - **`grafana` service:**
    - Pinned image `grafana/grafana-oss:<current 12.x>`, `ports: ["3000:3000"]`.
    - Mounts `./monitoring/grafana/provisioning:/etc/grafana/provisioning:ro` and `./monitoring/grafana_dashboard.json:/var/lib/grafana/dashboards/grafana_dashboard.json:ro`.
    - Environment: `GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD:-admin}`, `GF_AUTH_ANONYMOUS_ENABLED=true`, `GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer`, `GF_USERS_ALLOW_SIGN_UP=false`, `GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH=/var/lib/grafana/dashboards/grafana_dashboard.json`.
    - Named volume for `/var/lib/grafana`.
  - **`monitoring/prometheus.yml`:** target `etaflow:8000`, `metrics_path: /metrics/prometheus`, existing labels kept.
  - **Data source provisioning:** `name: Prometheus`, `type: prometheus`, `uid: prometheus`, `url: http://prometheus:9090`, `isDefault: true`.
  - **Dashboard provider:** `path: /var/lib/grafana/dashboards`.
  - **`.env.example`:** gains `GRAFANA_ADMIN_PASSWORD=` with a comment that it's required on the server.

- [ ] **Step 4: Bring the stack up and verify**

  Run: `docker compose up -d --build`, then check each of these:
  1. `curl -s http://127.0.0.1:8000/health` returns `"status": "healthy"` and `"artifacts_loaded": true`. This proves the models are in the image and the API is reachable from outside the container.
  2. Send the README payload to `POST /predict` 20 times.
  3. `curl -s http://127.0.0.1:9090/api/v1/targets` shows the `etaflow-prediction-api` target with `"health":"up"`.
  4. `curl -s "http://127.0.0.1:9090/api/v1/query?query=etaflow_http_requests_total"` returns a non-empty `result`.
  5. `curl -s http://127.0.0.1:3000/api/dashboards/uid/etaflow-prod-overview`, **without credentials**, returns 200, showing anonymous viewing works.
  6. `docker compose exec etaflow whoami` prints `etaflow`.

- [ ] **Step 5: Show Grafana in the browser pane** at `http://127.0.0.1:3000/d/etaflow-prod-overview`

  The panels must show data. Then run `docker compose down`.

- [ ] **Step 6: Commit**

  `git commit -m "feat(deploy): containerised app with provisioned Prometheus and Grafana"`

---

### Task 7: AWS stack, prod override and deploy scripts

**Files:**
- Create: `deploy/aws/etaflow-stack.yaml`, `docker-compose.prod.yml`, `deploy/remote-deploy.sh`
- Create: `deploy/aws/create-stack.ps1`, `deploy/aws/delete-stack.ps1`, `deploy/aws/deploy-now.ps1`, `deploy/aws/set-grafana-password.ps1`, `deploy/aws/stop-server.ps1`, `deploy/aws/start-server.ps1`

**Interfaces:**
- **Stack parameters:**
  - `InstanceType` (`t3.micro` | `t3.small`, default `t3.micro`)
  - `GitHubRepo` (default `chinmayeechoudhari/ETAFlow-Food-Delivery-Intelligence`)
  - `GitHubBranch` (default `main`)
  - `CreateGitHubOidcProvider` (`true` | `false`, default `true`)
  - `LatestAmiId` (`AWS::SSM::Parameter::Value<AWS::EC2::Image::Id>`, default `/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64`)
- **Stack outputs:** `DashboardUrl`, `GrafanaUrl`, `EcrRepositoryUri`, `InstanceId`, `BundleBucket`, `DeployRoleArn`, `Region`.
- **`deploy/remote-deploy.sh <image_uri> <region>`** runs as root in `/opt/etaflow`. Both `deploy-now.ps1` and `deploy.yml` (Task 8) run it after unpacking the bundle.
- **Bundle:** `tar.gz` of `docker-compose.yml`, `docker-compose.prod.yml`, `monitoring/` and `deploy/remote-deploy.sh`, uploaded to `s3://<BundleBucket>/bundle/<tag>.tar.gz`.

- [ ] **Step 1: `docker-compose.prod.yml`**

  - `etaflow`: `build: !reset null`, `image: ${ETAFLOW_IMAGE:?ETAFLOW_IMAGE must be set}`, `ports: !override ["80:8000"]`, `mem_limit: 512m`.
  - `prometheus`: `mem_limit: 192m`.
  - `grafana`: `environment` sets `GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD:?GRAFANA_ADMIN_PASSWORD must be set}`, and `mem_limit: 192m`.

- [ ] **Step 2: Verify that the override requires the password**

  - Run: `docker compose -f docker-compose.yml -f docker-compose.prod.yml config` with `ETAFLOW_IMAGE=x` and **no** `GRAFANA_ADMIN_PASSWORD`. Expected: a non-zero exit, with `GRAFANA_ADMIN_PASSWORD must be set` in the message.
  - With both variables set: it exits 0, the rendered `etaflow` has no `build`, and its port is `80:8000` only.

- [ ] **Step 3: `deploy/remote-deploy.sh`**

  - `set -euo pipefail`.
  - Reads the password with `aws ssm get-parameter --with-decryption --name /etaflow/grafana-admin-password`. If that fails, it **exits 1 with a clear message and changes nothing**.
  - Logs in to ECR for the image's registry.
  - Writes `/opt/etaflow/.env` (`ETAFLOW_IMAGE`, `GRAFANA_ADMIN_PASSWORD`) with mode 600.
  - Runs `docker compose -f docker-compose.yml -f docker-compose.prod.yml pull etaflow`, then `up -d --remove-orphans`, then `docker image prune -f`.
  - Check: `bash -n deploy/remote-deploy.sh` exits 0.

- [ ] **Step 4: `deploy/aws/etaflow-stack.yaml`**

  The resources are as in spec §6.7, plus:
  - **ECR:** `EmptyOnDelete: true`; lifecycle policy keeps the last 10 images.
  - **S3 bucket:** block all public access, SSE-S3, lifecycle rule expiring `bundle/` after 30 days.
  - **Security group:** ingress 80 and 3000 from `0.0.0.0/0`, nothing else.
  - **Instance role:** `AmazonSSMManagedInstanceCore`, `AmazonEC2ContainerRegistryReadOnly`, `s3:GetObject` on `bundle/*`, and `ssm:GetParameter` on `parameter/etaflow/*`.
  - **Instance:**
    - 20 GB gp3 root volume; `MetadataOptions` set to `HttpTokens: required`.
    - User-data installs `docker`, enables the service, installs the pinned Compose v2 plugin binary to `/usr/local/lib/docker/cli-plugins/`, creates a 2 GB swapfile, and runs `mkdir -p /opt/etaflow`.
  - **EIP** associated with the instance.
  - **OIDC provider** (conditional on `CreateGitHubOidcProvider`): `https://token.actions.githubusercontent.com`, audience `sts.amazonaws.com`.
  - **Deploy role:**
    - Trust: `token.actions.githubusercontent.com:sub` = `repo:${GitHubRepo}:ref:refs/heads/${GitHubBranch}` and `aud` = `sts.amazonaws.com`.
    - Permissions: `ecr:GetAuthorizationToken` on `*`; push actions on the repo ARN; `s3:PutObject` on `bundle/*`; `ssm:SendCommand` on the instance ARN and `arn:aws:ssm:${AWS::Region}::document/AWS-RunShellScript`; `ssm:GetCommandInvocation` on `*`.

- [ ] **Step 5: Lint the template**

  Run: `uvx cfn-lint deploy/aws/etaflow-stack.yaml`

  Expected: exit 0, no errors.

- [ ] **Step 6: PowerShell scripts**

  All take `-StackName etaflow -Region ap-south-1` defaults and read the outputs with `aws cloudformation describe-stacks`.
  - **`create-stack.ps1`:** runs `aws cloudformation deploy --capabilities CAPABILITY_NAMED_IAM`, then prints the outputs and the six GitHub repository variables `AWS_DEPLOY_ROLE_ARN`, `AWS_REGION`, `EC2_INSTANCE_ID`, `ECR_REPOSITORY_URI`, `BUNDLE_BUCKET` and `APP_URL`.
  - **`set-grafana-password.ps1`:** `Read-Host -AsSecureString` twice, which must match and be at least 12 characters, then `aws ssm put-parameter --type SecureString --overwrite`. Member 3 runs it personally.
  - **`deploy-now.ps1 [-Tag <git short sha>]`:** `docker build`; ECR login and push of `:<tag>` and `:latest`; builds the bundle with `tar.exe`; uploads it; `aws ssm send-command` with `AWS-RunShellScript` (download, unpack to `/opt/etaflow`, `bash deploy/remote-deploy.sh <uri>:<tag> <region>`); waits; prints stdout/stderr; then polls `<DashboardUrl>/health` for up to 120 s.
  - **`stop-server.ps1` / `start-server.ps1`:** `aws ec2 stop-instances` / `start-instances` plus `wait`.
  - **`delete-stack.ps1`:** asks the user to type the stack name to confirm, empties the bucket, runs `delete-stack`, then `wait stack-delete-complete`.
  - Check: `[System.Management.Automation.Language.Parser]::ParseFile()` reports 0 errors for each `.ps1`.

- [ ] **Step 7: Commit**

  `git commit -m "feat(deploy): CloudFormation EC2 stack, prod compose override and deploy scripts"`

---

### Task 8: Automatic deployment workflow

**Files:**
- Create: `.github/workflows/deploy.yml`
- Modify: `.github/workflows/ci.yml` (delete the `deploy-to-aws` job; nothing else)

**Interfaces:**
- Consumes: the workflow name `ETAFlow CI/CD Pipeline` from `ci.yml`; the repository variables from Task 7 Step 6; `deploy/remote-deploy.sh` and the bundle layout from Task 7.

- [ ] **Step 1: Write `deploy.yml`**

  - **Name:** `ETAFlow Deploy (AWS EC2)`.
  - **Triggers:** `workflow_run` (`workflows: ["ETAFlow CI/CD Pipeline"]`, `types: [completed]`, `branches: [main]`) and `workflow_dispatch`.
  - **Settings:** `concurrency: { group: deploy-ec2, cancel-in-progress: false }`; `permissions: { id-token: write, contents: read }`.
  - **Job `if`:** `(github.event_name == 'workflow_dispatch' || github.event.workflow_run.conclusion == 'success') && vars.AWS_DEPLOY_ROLE_ARN != ''`.
  - **Steps:**
    1. Checkout at `${{ github.event.workflow_run.head_sha || github.sha }}`.
    2. `aws-actions/configure-aws-credentials@v4` with `role-to-assume` and `aws-region` from the variables.
    3. `aws-actions/amazon-ecr-login@v2`.
    4. Build and push `${ECR_REPOSITORY_URI}:${sha}` and `:latest`.
    5. Tar and upload the bundle.
    6. `aws ssm send-command` with the same command as `deploy-now.ps1`.
    7. `aws ssm wait command-executed`, then `get-command-invocation`; fail unless the status is `Success`, printing both outputs.
    8. `curl --retry 12 --retry-delay 10 --retry-all-errors -fsS "$APP_URL/health"`.

- [ ] **Step 2: Remove the `deploy-to-aws` job from `ci.yml`**

- [ ] **Step 3: Lint the workflows**

  Run: `uvx --from actionlint-py actionlint .github/workflows/ci.yml .github/workflows/deploy.yml`

  Expected: no findings.

- [ ] **Step 4: Commit**

  `git commit -m "ci(deploy): deploy to EC2 via OIDC after CI passes; drop old ECR job from ci.yml"`

---

### Task 9: Documentation

**Files:**
- Create: `docs/DEPLOYMENT_GUIDE.md`
- Modify: `docs/AWS_CICD_DEPLOYMENT_GUIDE.md` (replace with a pointer plus the App Runner closure note), and `README.md` sections 6–7 (launch URL `http://127.0.0.1:8000/`, `/docs`, `docker compose up` with Grafana on `:3000`, the AWS section pointing to the guide)

- [ ] **Step 1: Write `DEPLOYMENT_GUIDE.md`**

  Cover these sections, in order:
  1. Architecture (text diagram: GitHub → ECR/S3 → SSM → EC2 compose: etaflow, prometheus, grafana).
  2. Costs (spec §10 table).
  3. One-time AWS setup:
     - root MFA;
     - the `etaflow-admin` IAM user with `AdministratorAccess` and MFA;
     - an access key, then `aws configure` with region `ap-south-1`.
  4. Create the stack (`create-stack.ps1`).
  5. Set the Grafana password (`set-grafana-password.ps1`).
  6. First deploy (`deploy-now.ps1`).
  7. GitHub automatic deploys: the six variables, which a repo admin sets under Settings → Secrets and variables → Actions → Variables.
  8. Demo URLs.
  9. Stop/start between demos.
  10. Delete everything.
  11. Troubleshooting: SSM command failed, target down in Prometheus, port 80 not reachable, out of memory → `t3.small`.

- [ ] **Step 2: Update the AWS guide pointer and the README sections**

- [ ] **Step 3: Verify the references**

  Every file path named in the three documents exists. Run `Select-String` over the docs for `deploy/aws/` and `.github/workflows/`, and `Test-Path` each match. Every command in the guide matches the real script parameters.

- [ ] **Step 4: Commit**

  `git commit -m "docs(deploy): EC2 deployment guide; correct launch and deployment docs"`

---

### Task 10: Go live (user-gated)

Each **[Member 3]** step is done by Member 3. Each **[approve]** step needs Member 3's explicit OK in chat before Claude runs it.

- [ ] **Step 1 [Member 3]: One-time AWS setup**

  Follow the DEPLOYMENT_GUIDE section 3 steps: root MFA, `etaflow-admin`, access key, then `aws configure`.

  Claude verifies: `aws sts get-caller-identity` shows `user/etaflow-admin`.

- [ ] **Step 2 [approve]: Create the stack**

  Claude restates the monthly cost, then runs `deploy/aws/create-stack.ps1`.

  Expected: `CREATE_COMPLETE`, with the outputs printed.

- [ ] **Step 3 [Member 3]: Set the Grafana password**

  Run `deploy/aws/set-grafana-password.ps1`.

- [ ] **Step 4 [approve]: First deploy**

  Run `deploy/aws/deploy-now.ps1`.

  Expected:
  - `<DashboardUrl>/health` → healthy.
  - `<DashboardUrl>/` loads the dashboard, checked in the browser pane.
  - `<DashboardUrl>/docs` loads.
  - `<GrafanaUrl>/d/etaflow-prod-overview` loads anonymously and shows data after a few predictions.

- [ ] **Step 5 [Member 3]: GitHub setup**

  Send the repo owner the six variable values printed by `create-stack.ps1`. Agree how `member3-deployment` reaches `main` (push access or a fork plus a PR).

  After the merge, the `ETAFlow Deploy (AWS EC2)` run must succeed.

- [ ] **Step 6: Wrap up**

  Run the full test suite and lint on the branch. Report the live URLs, and remind Member 3 about `stop-server.ps1` and `delete-stack.ps1`.

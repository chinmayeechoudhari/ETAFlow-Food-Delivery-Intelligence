"""FastAPI application for the ETAFlow prediction API and operations dashboard.

One server, one port: the JSON API, interactive docs (/docs), Prometheus metrics
(/metrics/prometheus) and the static dashboard from app/. Every API response keeps
the exact paths, status codes, bodies and CORS headers of the earlier
standard-library server, so existing clients and tests keep working.
"""

import json
import logging
from pathlib import Path
import socket
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import Headers, MutableHeaders
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send
import uvicorn

from etaflow import __version__
from etaflow.api.schema import ETAPredictionRequest
from etaflow.api.service import ArtifactUnavailableError, ETAPredictionService
from etaflow.api.telemetry import APIMetricsTracker, PrometheusMetrics

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]

ALLOWED_ORIGINS = {
    "http://127.0.0.1:8501",
    "http://localhost:8501",
}

REPORT_ENDPOINTS = {
    "/reports/experiments": "reports/experiments/experiment_summary.json",
    "/reports/drift": "reports/monitoring/drift_report.json",
    "/reports/reference-stats": "reports/monitoring/reference_stats.json",
    "/reports/validation": "reports/validation/data_validation_report.json",
    "/reports/registry": "models/registry.json",
}

API_PATHS = frozenset(
    {"/", "/predict", "/health", "/model-info", "/metrics", "/metrics/prometheus", *REPORT_ENDPOINTS}
)

PREDICT_EXAMPLE = {
    "restaurant_lat": 12.9352,
    "restaurant_lon": 77.6245,
    "customer_lat": 12.9550,
    "customer_lon": 77.6400,
    "order_hour": 20,
    "day_of_week": 4,
    "type_of_order": "Meal",
    "festival": "No",
    "city": "Metropolitian",
    "order_id": "KOR-DINNER-88",
}


class PredictRequestDoc(BaseModel):
    """Booking-time prediction request (documentation only; validation uses ETAPredictionRequest.from_dict)."""

    restaurant_lat: float = Field(..., description="Restaurant latitude")
    restaurant_lon: float = Field(..., description="Restaurant longitude")
    customer_lat: float = Field(..., description="Customer latitude")
    customer_lon: float = Field(..., description="Customer longitude")
    order_hour: int = Field(..., ge=0, le=23, description="Hour the order is placed (0-23)")
    day_of_week: int = Field(..., ge=0, le=6, description="Day of week (0=Monday ... 6=Sunday)")
    type_of_order: str = Field("Meal", description="Meal, Snack, Drinks or Buffet")
    festival: str = Field("No", description="Yes or No")
    city: str = Field("Metropolitian", description="Metropolitian, Urban or Semi-Urban")
    order_id: Optional[str] = Field(None, description="Optional caller reference echoed back")


def _cors_headers(origin: Optional[str]) -> List[Tuple[str, str]]:
    """CORS headers identical to the previous server's _send_cors_headers."""
    if origin in ALLOWED_ORIGINS:
        headers = [("Access-Control-Allow-Origin", origin), ("Vary", "Origin")]
    else:
        headers = [("Access-Control-Allow-Origin", "*")]
    headers.append(("Access-Control-Allow-Methods", "GET, POST, OPTIONS"))
    headers.append(("Access-Control-Allow-Headers", "Content-Type"))
    return headers


def _not_found_body(path: str) -> Dict[str, str]:
    return {"error": f"Endpoint '{path}' not found."}


class _CORSMiddleware:
    """Answers every OPTIONS preflight and adds the CORS headers to every response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        cors = _cors_headers(Headers(scope=scope).get("origin"))

        if scope["method"] == "OPTIONS":
            path = scope["path"].rstrip("/") or "/"
            if path in API_PATHS:
                response: Response = Response(status_code=204, headers=dict(cors))
            else:
                response = JSONResponse(_not_found_body(scope["path"]), status_code=404, headers=dict(cors))
            await response(scope, receive, send)
            return

        async def send_with_cors(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for key, value in cors:
                    headers[key] = value
            await send(message)

        await self.app(scope, receive, send_with_cors)


class _TrailingSlashMiddleware:
    """Lets '/health/' reach '/health' without a redirect, as the old server's rstrip('/') did."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            path = scope["path"]
            stripped = path.rstrip("/")
            if path != "/" and stripped != path and stripped in API_PATHS:
                scope = dict(scope)
                scope["path"] = stripped
        await self.app(scope, receive, send)


def create_app(
    service: Optional[ETAPredictionService] = None,
    telemetry: Optional[APIMetricsTracker] = None,
    metrics: Optional[PrometheusMetrics] = None,
    static_dir: Optional[Path] = None,
) -> FastAPI:
    """Build the ETAFlow FastAPI application."""
    if service is None:
        service = ETAPredictionService()
    if telemetry is None:
        telemetry = APIMetricsTracker()
    if metrics is None:
        metrics = PrometheusMetrics()
    if static_dir is None:
        static_dir = PROJECT_ROOT / "app"

    app = FastAPI(
        title="ETAFlow Prediction API",
        version=__version__,
        description="Booking-time food delivery ETA prediction with explainable attributions.",
        redirect_slashes=False,
    )
    app.state.service = service
    app.state.telemetry = telemetry
    app.state.metrics = metrics

    def record(status: int, latency_ms: Optional[float] = None, is_predict: bool = False) -> None:
        telemetry.record_request(status, latency_ms=latency_ms, is_predict=is_predict)
        metrics.record_request(status)

    def respond(status: int, body: Dict[str, Any], **record_kwargs: Any) -> JSONResponse:
        record(status, **record_kwargs)
        return JSONResponse(body, status_code=status)

    @app.get("/health", tags=["Service"])
    def health() -> JSONResponse:
        """Liveness and model readiness probe."""
        if service.is_ready:
            return respond(
                200,
                {"status": "healthy", "model_identity": service.model_identity, "artifacts_loaded": True},
            )
        return respond(
            503,
            {
                "status": "unhealthy",
                "error": "Model artifacts are not loaded or unavailable.",
                "artifacts_loaded": False,
            },
        )

    @app.get("/model-info", tags=["Service"])
    def model_info() -> JSONResponse:
        """Registry metadata for the served model."""
        return respond(200, service.get_model_info())

    @app.get("/metrics", tags=["Monitoring"])
    def metrics_json() -> JSONResponse:
        """Request counters and measured latency percentiles (JSON, used by the dashboard)."""
        return respond(200, telemetry.get_metrics())

    @app.get("/metrics/prometheus", tags=["Monitoring"])
    def metrics_prometheus() -> Response:
        """Prometheus text exposition, scraped by Prometheus for the Grafana dashboard."""
        body, content_type = metrics.render()
        record(200)
        return Response(content=body, media_type=content_type)

    def make_report_handler(rel_file: str) -> Callable[[], JSONResponse]:
        def report() -> JSONResponse:
            target_path = PROJECT_ROOT / rel_file
            if not target_path.is_file():
                return respond(404, {"error": f"Report file '{rel_file}' not found on server."})
            try:
                with open(target_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as exc:
                return JSONResponse({"error": f"Failed reading {rel_file}: {exc}"}, status_code=500)
            return respond(200, data)

        return report

    for route_path, rel_file in REPORT_ENDPOINTS.items():
        app.add_api_route(
            route_path,
            make_report_handler(rel_file),
            methods=["GET"],
            tags=["MLOps reports"],
            summary=f"Serve {rel_file}",
        )

    @app.post(
        "/predict",
        tags=["Prediction"],
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": PredictRequestDoc.model_json_schema(),
                        "example": PREDICT_EXAMPLE,
                    }
                },
            }
        },
    )
    async def predict(request: Request) -> JSONResponse:
        """Predict total delivery duration at booking time, with local feature attributions."""
        t0 = time.perf_counter()

        def elapsed_ms() -> float:
            return (time.perf_counter() - t0) * 1000.0

        raw = await request.body()
        if not raw:
            return respond(400, {"error": "Missing Content-Length header or empty body."}, is_predict=True)

        try:
            payload = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError, RecursionError) as exc:
            return respond(400, {"error": "Invalid JSON payload.", "details": [str(exc)]}, is_predict=True)

        try:
            eta_request, errors = ETAPredictionRequest.from_dict(payload)
        except (OverflowError, TypeError, ValueError) as exc:
            # e.g. "order_hour": Infinity or 1e400 parse as float('inf') and overflow int()
            eta_request, errors = None, [f"Invalid field value: {exc}"]
        if errors or eta_request is None:
            return respond(400, {"error": "Validation failed", "details": errors}, is_predict=True)

        try:
            response = await run_in_threadpool(service.predict, eta_request)
        except ArtifactUnavailableError:
            return respond(
                503,
                {"error": "Prediction service is unavailable: Model artifacts are not loaded."},
                latency_ms=elapsed_ms(),
                is_predict=True,
            )
        except Exception as exc:
            logger.error("Unexpected error during prediction: %s", exc, exc_info=False)
            return respond(
                500,
                {"error": "Internal prediction service error."},
                latency_ms=elapsed_ms(),
                is_predict=True,
            )

        latency_ms = elapsed_ms()
        metrics.record_prediction(latency_ms / 1000.0, response.predicted_duration_minutes)
        return respond(200, response.to_dict(), latency_ms=latency_ms, is_predict=True)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if exc.status_code in (404, 405):
            return respond(404, _not_found_body(request.url.path))
        return JSONResponse({"error": str(exc.detail)}, status_code=exc.status_code)

    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="dashboard")

    app.add_middleware(_TrailingSlashMiddleware)
    app.add_middleware(_CORSMiddleware)
    return app


class ServerHandle:
    """Runs the app with uvicorn behind the serve_forever/shutdown/server_close interface of http.server."""

    def __init__(self, app: FastAPI, host: str, port: int) -> None:
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.bind((host, port))
        self._socket.listen(128)
        self.server_address: Tuple[str, int] = self._socket.getsockname()[:2]
        self._server = uvicorn.Server(uvicorn.Config(app, log_level="warning", lifespan="off"))
        self._stopped = threading.Event()

    def serve_forever(self) -> None:
        try:
            self._server.run(sockets=[self._socket])
        finally:
            self._stopped.set()

    def shutdown(self) -> None:
        self._server.should_exit = True
        self._stopped.wait(timeout=10)

    def server_close(self) -> None:
        try:
            self._socket.close()
        except OSError:
            pass


def create_api_server(
    service: Optional[ETAPredictionService] = None,
    host: str = "127.0.0.1",
    port: int = 8000,
    telemetry: Optional[APIMetricsTracker] = None,
) -> ServerHandle:
    """Create a server for the app bound to (host, port); port 0 picks a free port."""
    return ServerHandle(create_app(service=service, telemetry=telemetry), host, port)


def run_server(
    service: Optional[ETAPredictionService] = None,
    host: str = "127.0.0.1",
    port: int = 8000,
    telemetry: Optional[APIMetricsTracker] = None,
) -> None:
    """Run the prediction API and dashboard until interrupted."""
    app = create_app(service=service, telemetry=telemetry)
    print(f"ETAFlow serving at http://{host}:{port}/")
    print("Available endpoints:")
    print(f"  GET  http://{host}:{port}/            (operations dashboard)")
    print(f"  GET  http://{host}:{port}/docs        (interactive API docs)")
    print(f"  GET  http://{host}:{port}/health")
    print(f"  GET  http://{host}:{port}/model-info")
    print(f"  GET  http://{host}:{port}/metrics")
    print(f"  GET  http://{host}:{port}/metrics/prometheus")
    print(f"  POST http://{host}:{port}/predict")
    uvicorn.run(app, host=host, port=port, log_level="info")

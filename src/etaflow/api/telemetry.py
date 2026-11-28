"""Real-time API performance telemetry and latency monitoring for ETAFlow."""

from collections import deque
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import threading
import time
from typing import Any, Dict, Iterator, List, Optional, Tuple

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    PlatformCollector,
    ProcessCollector,
    generate_latest,
)
from prometheus_client.core import GaugeMetricFamily
from prometheus_client.registry import Collector

DEFAULT_DRIFT_REPORT_PATH = Path(__file__).resolve().parents[3] / "reports" / "monitoring" / "drift_report.json"

INFERENCE_LATENCY_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5)


class APIMetricsTracker:
    """Thread-safe collector for real request latency and endpoint telemetry."""

    def __init__(self, max_history: int = 2000) -> None:
        self._lock = threading.Lock()
        self.start_time = datetime.now(timezone.utc)
        self.start_timestamp = time.time()
        self.total_requests = 0
        self.successful_predictions = 0
        self.failed_predictions = 0
        self.latencies_ms: deque = deque(maxlen=max_history)
        self.status_code_counts: Dict[str, int] = {}

    def record_request(
        self,
        status_code: int,
        latency_ms: Optional[float] = None,
        is_predict: bool = False,
    ) -> None:
        """Record an incoming request completion.

        Args:
            status_code: HTTP response status code.
            latency_ms: Measured wall-clock duration in milliseconds.
            is_predict: True if request was to the /predict endpoint.
        """
        with self._lock:
            self.total_requests += 1
            code_str = str(status_code)
            self.status_code_counts[code_str] = self.status_code_counts.get(code_str, 0) + 1

            if is_predict:
                if 200 <= status_code < 300:
                    self.successful_predictions += 1
                else:
                    self.failed_predictions += 1

                if latency_ms is not None and latency_ms >= 0:
                    self.latencies_ms.append(float(latency_ms))

    def _compute_percentile(self, sorted_vals: List[float], percentile: float) -> float:
        """Calculate percentile from a sorted list."""
        if not sorted_vals:
            return 0.0
        k = (len(sorted_vals) - 1) * (percentile / 100.0)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return sorted_vals[int(k)]
        d0 = sorted_vals[int(f)] * (c - k)
        d1 = sorted_vals[int(c)] * (k - f)
        return d0 + d1

    def get_metrics(self) -> Dict[str, Any]:
        """Compute aggregated latency and throughput metrics.

        Returns:
            Dictionary with measured latency percentiles, error rates, and request counts.
        """
        with self._lock:
            uptime = max(0.001, time.time() - self.start_timestamp)
            uptime_min = uptime / 60.0
            rpm = round(self.total_requests / uptime_min, 2) if uptime_min > 0 else 0.0

            total_preds = self.successful_predictions + self.failed_predictions
            error_rate = (
                round((self.failed_predictions / total_preds) * 100.0, 2)
                if total_preds > 0
                else 0.0
            )

            lat_list = list(self.latencies_ms)
            if lat_list:
                sorted_lats = sorted(lat_list)
                latest_lat = round(lat_list[-1], 2)
                mean_lat = round(sum(lat_list) / len(lat_list), 2)
                min_lat = round(min(lat_list), 2)
                max_lat = round(max(lat_list), 2)
                p50 = round(self._compute_percentile(sorted_lats, 50.0), 2)
                p90 = round(self._compute_percentile(sorted_lats, 90.0), 2)
                p95 = round(self._compute_percentile(sorted_lats, 95.0), 2)
                p99 = round(self._compute_percentile(sorted_lats, 99.0), 2)
            else:
                latest_lat = 0.0
                mean_lat = 0.0
                min_lat = 0.0
                max_lat = 0.0
                p50 = 0.0
                p90 = 0.0
                p95 = 0.0
                p99 = 0.0

            return {
                "server_start_time_utc": self.start_time.isoformat(),
                "uptime_seconds": round(uptime, 2),
                "total_requests": self.total_requests,
                "successful_predictions": self.successful_predictions,
                "failed_predictions": self.failed_predictions,
                "error_rate_pct": error_rate,
                "requests_per_minute": rpm,
                "status_code_counts": dict(self.status_code_counts),
                "sample_count": len(lat_list),
                "latency_ms": {
                    "latest": latest_lat,
                    "mean": mean_lat,
                    "min": min_lat,
                    "max": max_lat,
                    "p50": p50,
                    "p90": p90,
                    "p95": p95,
                    "p99": p99,
                },
            }


class _DriftFlagCollector(Collector):
    """Reads the latest drift report at scrape time and exposes it as a 0/1 gauge."""

    def __init__(self, drift_report_path: Path) -> None:
        self.drift_report_path = drift_report_path

    def _drift_detected(self) -> float:
        try:
            with open(self.drift_report_path, "r", encoding="utf-8") as f:
                report = json.load(f)
            status = report["clean_batch_results"]["overall_status"]
        except (OSError, ValueError, KeyError, TypeError):
            return 0.0
        return 0.0 if status == "STABLE" else 1.0

    def collect(self) -> Iterator[GaugeMetricFamily]:
        yield GaugeMetricFamily(
            "etaflow_data_drift_detected_flag",
            "1 when the latest drift report flags the clean batch as drifted, otherwise 0.",
            value=self._drift_detected(),
        )


class PrometheusMetrics:
    """Prometheus metrics for the prediction API, named to match monitoring/grafana_dashboard.json."""

    def __init__(self, drift_report_path: Optional[Path] = None) -> None:
        self.registry = CollectorRegistry()
        ProcessCollector(registry=self.registry)
        PlatformCollector(registry=self.registry)
        self.http_requests = Counter(
            "etaflow_http_requests",
            "API requests handled, by HTTP status code.",
            ["status"],
            registry=self.registry,
        )
        self.inference_duration = Histogram(
            "etaflow_inference_duration_seconds",
            "Wall-clock duration of successful /predict requests.",
            buckets=INFERENCE_LATENCY_BUCKETS,
            registry=self.registry,
        )
        self.predicted_duration = Gauge(
            "etaflow_predicted_duration_minutes",
            "Most recent predicted delivery duration in minutes.",
            registry=self.registry,
        )
        self.registry.register(_DriftFlagCollector(Path(drift_report_path or DEFAULT_DRIFT_REPORT_PATH)))

    def record_request(self, status_code: int) -> None:
        """Count one handled API request under its status code."""
        self.http_requests.labels(status=str(int(status_code))).inc()

    def record_prediction(self, latency_seconds: float, predicted_minutes: float) -> None:
        """Record latency and the predicted ETA of one successful prediction."""
        self.inference_duration.observe(max(0.0, float(latency_seconds)))
        self.predicted_duration.set(float(predicted_minutes))

    def render(self) -> Tuple[bytes, str]:
        """Return the Prometheus text exposition body and its content type."""
        return generate_latest(self.registry), CONTENT_TYPE_LATEST

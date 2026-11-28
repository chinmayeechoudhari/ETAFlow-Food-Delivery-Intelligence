"""Tests for Member 3 deployment work: Prometheus metrics, FastAPI serving, and bind settings."""

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
from typing import List, Optional, Tuple
import unittest
import urllib.request

from fastapi.testclient import TestClient

from etaflow.api.app import create_api_server, create_app
from etaflow.api.service import ETAPredictionService
from etaflow.api.settings import resolve_bind_address
from etaflow.api.telemetry import PrometheusMetrics

# README example payload for POST /predict
VALID = {
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


def _post_json(url: str, payload: dict) -> int:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status


def _get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


class TestPrometheusMetrics(unittest.TestCase):
    """PrometheusMetrics exposes exactly the metric names the Grafana dashboard queries."""

    def _write_report(self, tmp: Path, status: str) -> Path:
        p = tmp / "drift_report.json"
        p.write_text(json.dumps({"clean_batch_results": {"overall_status": status}}), encoding="utf-8")
        return p

    def test_render_contains_all_grafana_metrics(self) -> None:
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

    def test_drift_flag_follows_report(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            stable = PrometheusMetrics(self._write_report(Path(d), "STABLE")).render()[0].decode()
            self.assertIn("etaflow_data_drift_detected_flag 0.0", stable)
            drift = PrometheusMetrics(self._write_report(Path(d), "DRIFT_DETECTED")).render()[0].decode()
            self.assertIn("etaflow_data_drift_detected_flag 1.0", drift)

    def test_drift_flag_missing_or_corrupt_report(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / "drift_report.json"
            bad.write_text("{not json", encoding="utf-8")
            for path in (bad, Path(d) / "absent.json"):
                text = PrometheusMetrics(path).render()[0].decode()
                self.assertIn("etaflow_data_drift_detected_flag 0.0", text)

    def test_two_instances_do_not_collide(self) -> None:
        PrometheusMetrics()
        PrometheusMetrics()  # must not raise duplicate-registration errors


class TestFastAPIApp(unittest.TestCase):
    """The FastAPI app serves the API, docs, Prometheus metrics and the dashboard on one port."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.service = ETAPredictionService()
        cls.client = TestClient(create_app(service=cls.service))

    def test_docs_and_openapi_available(self) -> None:
        docs = self.client.get("/docs")
        self.assertEqual(docs.status_code, 200)
        self.assertIn("text/html", docs.headers["content-type"])
        spec = self.client.get("/openapi.json")
        self.assertEqual(spec.status_code, 200)
        self.assertIn("/predict", spec.json()["paths"])

    def test_root_serves_dashboard(self) -> None:
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Dispatch Control Center", resp.text)

    def test_static_asset_served(self) -> None:
        resp = self.client.get("/app.js")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("API_BASE_URL", resp.text)

    def test_prometheus_endpoint_counts_predictions(self) -> None:
        client = TestClient(create_app(service=self.service))
        self.assertEqual(client.post("/predict", json=VALID).status_code, 200)
        resp = client.get("/metrics/prometheus")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.headers["content-type"].startswith("text/plain"))
        self.assertIn("etaflow_inference_duration_seconds_count 1.0", resp.text)
        self.assertIn('status="200"', resp.text)

    def test_metrics_json_unchanged(self) -> None:
        body = self.client.get("/metrics").json()
        self.assertIn("latency_ms", body)
        self.assertIn("total_requests", body)

    def test_trailing_slash_not_redirected(self) -> None:
        resp = self.client.get("/health/", follow_redirects=False)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "healthy")

    def test_unknown_path_json_404(self) -> None:
        resp = self.client.get("/nope")
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json(), {"error": "Endpoint '/nope' not found."})

    def test_non_utf8_body_returns_400(self) -> None:
        resp = self.client.post(
            "/predict",
            content=b"\xff\xfe\x00",
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.json())

    def test_non_finite_numbers_return_400(self) -> None:
        base = '"restaurant_lat": 12.9352, "restaurant_lon": 77.6245, "customer_lat": 12.955, "customer_lon": 77.64'
        for bad_hour in ("Infinity", "1e400", "NaN"):
            raw = ("{" + base + ', "order_hour": ' + bad_hour + ', "day_of_week": 4}').encode("utf-8")
            resp = self.client.post("/predict", content=raw, headers={"Content-Type": "application/json"})
            self.assertEqual(resp.status_code, 400, bad_hour)
            self.assertIn("error", resp.json())

    def test_deeply_nested_json_returns_400(self) -> None:
        resp = self.client.post("/predict", content=b"[" * 100000, headers={"Content-Type": "application/json"})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error"], "Invalid JSON payload.")

    def test_static_path_traversal_blocked(self) -> None:
        for path in ("/../configs/config.yaml", "/..%2fconfigs%2fconfig.yaml", "/%2e%2e/configs/config.yaml"):
            resp = self.client.get(path)
            self.assertEqual(resp.status_code, 404, path)
            self.assertNotIn("model_name", resp.text, path)

    def test_concurrent_predictions_all_succeed(self) -> None:
        server = create_api_server(service=self.service, host="127.0.0.1", port=0)
        base = f"http://127.0.0.1:{server.server_address[1]}"
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            before = _get_json(f"{base}/metrics")["successful_predictions"]
            with ThreadPoolExecutor(max_workers=10) as pool:
                statuses = list(pool.map(lambda _: _post_json(f"{base}/predict", VALID), range(20)))
            self.assertEqual(statuses, [200] * 20)
            after = _get_json(f"{base}/metrics")["successful_predictions"]
            self.assertEqual(after, before + 20)
        finally:
            server.shutdown()
            server.server_close()

    def test_server_handle_lifecycle(self) -> None:
        handle = create_api_server(service=self.service, host="127.0.0.1", port=0)
        self.assertGreater(handle.server_address[1], 0)
        thread = threading.Thread(target=handle.serve_forever, daemon=True)
        thread.start()
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{handle.server_address[1]}/health", timeout=30) as resp:
                self.assertEqual(resp.status, 200)
        finally:
            handle.shutdown()
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
            handle.server_close()


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TestDeploymentConfig(unittest.TestCase):
    """Guards on the deploy workflow, CloudFormation template and server deploy script."""

    def test_deploy_workflow_only_deploys_pushes_to_main_of_this_repo(self) -> None:
        import yaml

        wf = yaml.safe_load((PROJECT_ROOT / ".github/workflows/deploy.yml").read_text(encoding="utf-8"))
        cond = " ".join(wf["jobs"]["deploy"]["if"].split())
        for required in (
            "github.event.workflow_run.event == 'push'",
            "github.event.workflow_run.head_branch == 'main'",
            "github.event.workflow_run.head_repository.full_name == github.repository",
            "vars.AWS_DEPLOY_ROLE_ARN != ''",
        ):
            self.assertIn(required, cond)

    def test_stack_pins_the_server_image(self) -> None:
        """A server image resolved on every stack update would replace the server (and its data)."""
        import yaml

        class CfnLoader(yaml.SafeLoader):
            pass

        CfnLoader.add_multi_constructor("!", lambda loader, suffix, node: None)
        text = (PROJECT_ROOT / "deploy/aws/etaflow-stack.yaml").read_text(encoding="utf-8")
        params = yaml.load(text, Loader=CfnLoader)["Parameters"]
        self.assertNotIn("LatestAmiId", params)
        self.assertEqual(params["AmiId"]["Type"], "AWS::EC2::Image::Id")

    def test_deploy_role_trusts_githubs_id_based_subject(self) -> None:
        """GitHub's OIDC token for this repo carries owner and repo ids, e.g. (seen in CloudTrail):
        repo:chinmayeechoudhari@190323353/ETAFlow-Food-Delivery-Intelligence@1452948068:ref:refs/heads/main
        """
        import yaml

        class CfnLoader(yaml.SafeLoader):
            pass

        def construct_tagged(loader, suffix, node):
            if isinstance(node, yaml.ScalarNode):
                return loader.construct_scalar(node)
            if isinstance(node, yaml.SequenceNode):
                return loader.construct_sequence(node, deep=True)
            return loader.construct_mapping(node, deep=True)

        CfnLoader.add_multi_constructor("!", construct_tagged)
        tpl = yaml.load((PROJECT_ROOT / "deploy/aws/etaflow-stack.yaml").read_text(encoding="utf-8"), Loader=CfnLoader)
        params = tpl["Parameters"]
        self.assertEqual(params["GitHubOwnerId"]["Default"], "190323353")
        self.assertEqual(params["GitHubRepoId"]["Default"], "1452948068")
        condition = tpl["Resources"]["GitHubDeployRole"]["Properties"]["AssumeRolePolicyDocument"]["Statement"][0][
            "Condition"
        ]["StringEquals"]
        subjects = [s[0] if isinstance(s, list) else s for s in condition["token.actions.githubusercontent.com:sub"]]
        self.assertIn("repo:${GitHubRepo}:ref:refs/heads/${GitHubBranch}", subjects)
        self.assertIn("repo:${Owner}@${GitHubOwnerId}/${Name}@${GitHubRepoId}:ref:refs/heads/${GitHubBranch}", subjects)

    def test_shell_scripts_always_check_out_with_lf(self) -> None:
        """A Windows clone with core.autocrlf=true must not turn remote-deploy.sh into CRLF (bash fails on \\r)."""
        out = subprocess.run(
            ["git", "check-attr", "eol", "--", "deploy/remote-deploy.sh", "start.sh"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        self.assertIn("deploy/remote-deploy.sh: eol: lf", out)
        self.assertIn("start.sh: eol: lf", out)


def _find_bash() -> Optional[str]:
    """Git Bash on Windows (not the WSL launcher in System32), plain bash elsewhere."""
    if os.name == "nt":
        for candidate in (r"C:\Program Files\Git\bin\bash.exe", r"C:\Program Files (x86)\Git\bin\bash.exe"):
            if Path(candidate).exists():
                return candidate
        return None
    return shutil.which("bash")


@unittest.skipIf(_find_bash() is None, "bash not available")
class TestRemoteDeployScript(unittest.TestCase):
    """Runs deploy/remote-deploy.sh against stand-in aws/docker/cloud-init commands that log their calls."""

    IMAGE = "123456789012.dkr.ecr.ap-south-1.amazonaws.com/etaflow-app:abc123"

    def _run(self, tmp: Path, password: Optional[str]) -> Tuple[subprocess.CompletedProcess, List[str], Path]:
        fake = tmp / "fakebin"
        fake.mkdir()
        app_dir = tmp / "opt"
        app_dir.mkdir()
        log = (tmp / "calls.log").as_posix()
        get_param = f"echo {password}" if password else "exit 255"
        scripts = {
            "aws": f'#!/bin/sh\necho "aws $*" >> "{log}"\ncase "$*" in\n'
            f"  *get-parameter*) {get_param} ;;\n  *get-login-password*) echo token ;;\nesac\n",
            "docker": f'#!/bin/sh\necho "docker $*" >> "{log}"\ncat > /dev/null 2>&1 || true\n',
            "cloud-init": f'#!/bin/sh\necho "cloud-init $*" >> "{log}"\n',
        }
        for name, body in scripts.items():
            path = fake / name
            path.write_bytes(body.encode("utf-8"))
            path.chmod(0o755)
        env = dict(os.environ, ETAFLOW_APP_DIR=app_dir.as_posix())
        env["PATH"] = str(fake) + os.pathsep + env.get("PATH", "")
        script = (PROJECT_ROOT / "deploy" / "remote-deploy.sh").as_posix()
        proc = subprocess.run(
            [_find_bash(), script, self.IMAGE, "ap-south-1"],
            env=env,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=60,
        )
        calls = (tmp / "calls.log").read_text(encoding="utf-8").splitlines() if (tmp / "calls.log").exists() else []
        return proc, calls, app_dir

    def test_refuses_without_grafana_password(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            proc, calls, app_dir = self._run(Path(d), password=None)
            self.assertEqual(proc.returncode, 1, proc.stderr)
            self.assertFalse([c for c in calls if c.startswith("docker") and "compose version" not in c])
            self.assertFalse((app_dir / ".env").exists())

    def test_prunes_all_unused_images(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            proc, calls, app_dir = self._run(Path(d), password="s3cret-password-123")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("docker image prune -af", calls)
            self.assertIn(f"ETAFLOW_IMAGE='{self.IMAGE}'", (app_dir / ".env").read_text(encoding="utf-8"))

    def test_waits_for_server_bootstrap_before_docker(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            proc, calls, _ = self._run(Path(d), password="s3cret-password-123")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("cloud-init status --wait", calls)
            first_docker = next(i for i, c in enumerate(calls) if c.startswith("docker"))
            self.assertLess(calls.index("cloud-init status --wait"), first_docker)


class TestBindAddress(unittest.TestCase):
    """Bind address precedence: CLI flags > API_HOST/API_PORT > config.yaml > defaults."""

    def test_defaults(self) -> None:
        self.assertEqual(resolve_bind_address(None, None, {}, {}), ("127.0.0.1", 8000))

    def test_config_used(self) -> None:
        self.assertEqual(
            resolve_bind_address(None, None, {"host": "127.0.0.1", "port": 9000}, {}),
            ("127.0.0.1", 9000),
        )

    def test_env_overrides_config(self) -> None:
        self.assertEqual(
            resolve_bind_address(
                None, None, {"host": "127.0.0.1", "port": 9000}, {"API_HOST": "0.0.0.0", "API_PORT": "8000"}
            ),
            ("0.0.0.0", 8000),
        )

    def test_cli_overrides_env(self) -> None:
        self.assertEqual(
            resolve_bind_address("127.0.0.2", 7000, {}, {"API_HOST": "0.0.0.0", "API_PORT": "8000"}),
            ("127.0.0.2", 7000),
        )

    def test_bad_env_port(self) -> None:
        with self.assertRaisesRegex(ValueError, "API_PORT must be an integer, got 'abc'"):
            resolve_bind_address(None, None, {}, {"API_PORT": "abc"})


if __name__ == "__main__":
    unittest.main()

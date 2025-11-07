import os
import time
import socket
import json
import pytest
import httpx

# Integration test: requires API reachable (e.g., via docker-compose up)
pytestmark = pytest.mark.integration

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
API_PORT = int(os.getenv("API_PORT", "8000"))

VALID_QASM3 = json.loads(open(os.path.join(os.path.dirname(__file__), "qc_example.json"), "r").read())["qc"].strip()


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def _wait_for_api(timeout=15):
    start = time.time()
    with httpx.Client() as client:
        while time.time() - start < timeout:
            if _port_open("localhost", API_PORT):
                try:
                    r = client.get(f"http://localhost:{API_PORT}/docs", timeout=1.0)
                    if r.status_code == 200:
                        return True
                except Exception:
                    pass
            time.sleep(0.5)
    return False


@pytest.fixture(scope="module")
def ensure_api():
    if not _wait_for_api():
        pytest.skip("API not reachable on expected port; run docker-compose up first.")


def test_full_submit_and_retrieve(ensure_api):
    with httpx.Client() as client:
        resp = client.post(f"http://localhost:{API_PORT}/tasks", json={"qc": VALID_QASM3})
        assert resp.status_code == 200, resp.text
        task_id = resp.json()["task_id"]

        deadline = time.time() + 30
        result_payload = None
        while time.time() < deadline:
            r = client.get(f"http://localhost:{API_PORT}/tasks/{task_id}")
            assert r.status_code == 200
            data = r.json()
            if data["status"] == "completed":
                result_payload = data["result"]
                break
            elif data["status"] == "error":
                pytest.fail(f"Task errored prematurely: {data}")
            time.sleep(1)
        assert result_payload is not None, "Task did not complete in time"
        assert isinstance(result_payload, dict)
        for k in result_payload.keys():
            assert set(k).issubset({"0", "1"})

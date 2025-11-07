from typing import Any, Dict
from pathlib import Path
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Import the routes module to patch its internals
import app.routes as routes
from app.settings import QC_TASK_MAX_RETRIES, QC_TASK_TIME_LIMIT_MS
from dramatiq.results import ResultMissing, ResultTimeout


class DummyRedis:
    def __init__(self):
        self.store: Dict[str, bytes] = {}
        self.last_px: int | None = None

    def set(self, key: str, value: bytes, px: int | None = None):  # value comes in as bytes
        self.store[key] = value if isinstance(value, bytes) else bytes(value)
        self.last_px = px

    def get(self, key: str):
        return self.store.get(key)

    def delete(self, key: str):
        self.store.pop(key, None)


@pytest.fixture(autouse=True)
def patch_redis(monkeypatch):
    dummy = DummyRedis()
    monkeypatch.setattr(routes, "redis_client", dummy)
    return dummy


@pytest.fixture
def app_client(monkeypatch) -> TestClient:
    # Patch broker.enqueue to avoid real Redis/network
    def fake_enqueue(msg):
        pass

    monkeypatch.setattr(routes.broker, "enqueue", fake_enqueue)

    # Patch actor message creation to avoid dramatiq internals
    class FakeMsg:
        def __init__(self, message_id: str):
            self.message_id = message_id

    def fake_message(task_id: str, qasm3_str: str):  # signatures match usage
        return FakeMsg("dummy-id")

    monkeypatch.setattr(routes.qasm3_task, "message", fake_message)

    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app)


def test_post_task_success(app_client, patch_redis):
    # Load a valid QASM3 program from fixture file
    qc_body = json.loads(Path(__file__).with_name("qc_example.json").read_text())
    resp = app_client.post("/tasks", json=qc_body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_id"] == "dummy-id"
    assert data["message"] == "Task submitted successfully."
    # Existence key set with expected TTL
    expected_ttl = QC_TASK_TIME_LIMIT_MS * QC_TASK_MAX_RETRIES
    key = routes._submitted_key("dummy-id")
    assert key in patch_redis.store
    assert patch_redis.last_px == expected_ttl


def test_post_task_empty_qc(app_client):
    resp = app_client.post("/tasks", json={"qc": "   "})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "QASM3 code cannot be empty"


def test_post_task_missing_field(app_client):
    resp = app_client.post("/tasks", json={})
    # FastAPI validation error
    assert resp.status_code == 422


def test_post_task_invalid_qasm3(app_client, monkeypatch):
    # Force qiskit.qasm3.loads to raise
    def fake_loads(_):
        raise ValueError("parse error")

    monkeypatch.setattr(routes.qiskit.qasm3, "loads", fake_loads)
    resp = app_client.post("/tasks", json={"qc": "INVALID"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "QASM3 code is not valid"


@pytest.fixture
def patch_message_success(monkeypatch):
    class SuccessMessage:
        def __init__(self, **_: Any):
            pass

        def get_result(self, backend, block=False):  # noqa: D401
            return {"0": 10, "1": 5}

    monkeypatch.setattr(routes, "Message", SuccessMessage)


@pytest.fixture
def patch_message_bytes(monkeypatch):
    class BytesMessage:
        def __init__(self, **_: Any):
            pass

        def get_result(self, backend, block=False):
            return b"{\"0\": 10, \"1\": 5}"

    monkeypatch.setattr(routes, "Message", BytesMessage)


@pytest.fixture
def patch_message_missing(monkeypatch):
    class MissingMessage:
        def __init__(self, **_: Any):
            pass

        def get_result(self, backend, block=False):
            raise ResultMissing("missing")

    monkeypatch.setattr(routes, "Message", MissingMessage)


@pytest.fixture
def patch_message_timeout(monkeypatch):
    class TimeoutMessage:
        def __init__(self, **_: Any):
            pass

        def get_result(self, backend, block=False):
            raise ResultTimeout("timeout")

    monkeypatch.setattr(routes, "Message", TimeoutMessage)


def test_get_task_completed(app_client, patch_message_success, patch_redis):
    # Pretend task was submitted (key present) though not required for completion path
    patch_redis.set(routes._submitted_key("dummy-id"), b"1")
    resp = app_client.get("/tasks/dummy-id")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["result"] == {"0": 10, "1": 5}
    # Existence key removed
    assert routes._submitted_key("dummy-id") not in patch_redis.store


def test_get_task_completed_bytes_decode(app_client, patch_message_bytes, patch_redis):
    patch_redis.set(routes._submitted_key("dummy-id"), b"1")
    resp = app_client.get("/tasks/dummy-id")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    # Since we returned a JSON-like bytes string, the route decodes it but does not JSON-parse.
    # So the raw decoded string should be returned.
    assert isinstance(data["result"], dict)
    assert data["result"] == {"0": 10, "1": 5}


def test_get_task_pending_missing_result(app_client, patch_message_missing, patch_redis):
    patch_redis.set(routes._submitted_key("dummy-id"), b"1")
    resp = app_client.get("/tasks/dummy-id")
    assert resp.status_code == 200
    assert resp.json() == {"status": "pending", "message": "Task is still in progress."}


def test_get_task_not_found_missing_result(app_client, patch_message_missing):
    resp = app_client.get("/tasks/dummy-id")
    assert resp.status_code == 200
    assert resp.json() == {"status": "error", "message": "Task not found."}


def test_get_task_pending_timeout(app_client, patch_message_timeout, patch_redis):
    patch_redis.set(routes._submitted_key("dummy-id"), b"1")
    resp = app_client.get("/tasks/dummy-id")
    assert resp.status_code == 200
    assert resp.json() == {"status": "pending", "message": "Task is still in progress."}


def test_get_task_not_found_timeout(app_client, patch_message_timeout):
    resp = app_client.get("/tasks/dummy-id")
    assert resp.status_code == 200
    assert resp.json() == {"status": "error", "message": "Task not found."}

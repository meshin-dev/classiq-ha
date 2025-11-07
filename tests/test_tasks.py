from pathlib import Path
import json
import pytest

import app.tasks as tasks_module

# Access the actor's underlying function via .fn
qasm3_actor = tasks_module.qasm3_task
qasm3_fn = qasm3_actor.fn  # underlying callable


class DummyRedis:
    def __init__(self):
        self.deleted_keys = []
        self.store: dict[str, bytes] = {}

    def delete(self, key: str):
        self.deleted_keys.append(key)
        self.store.pop(key, None)

    def set(self, key: str, value: bytes):
        self.store[key] = value


@pytest.fixture(autouse=True)
def patch_redis_client(monkeypatch):
    dummy = DummyRedis()
    monkeypatch.setattr(tasks_module, "redis_client", dummy)
    return dummy


@pytest.fixture
def valid_qasm3() -> str:
    qc_body = json.loads(Path(__file__).with_name("qc_example.json").read_text())
    return qc_body["qc"].strip()


# Aer simulator patches (we keep these for performance determinism) -------------------------------------------------
@pytest.fixture
def patch_aer_success(monkeypatch):
    class FakeResult:
        def get_counts(self):
            # Return Bell state style counts (approximate split) but deterministic
            return {"00": 5, "11": 3}

    class FakeJob:
        def __init__(self, shots: int):
            self.shots = shots

        def result(self):  # noqa: D401
            return FakeResult()

    class FakeSimulator:
        def __init__(self):
            self.last_shots = None

        def run(self, circuit, shots: int):  # noqa: D401
            self.last_shots = shots
            return FakeJob(shots)

    fake_sim = FakeSimulator()

    def fake_aer_simulator():
        return fake_sim

    monkeypatch.setattr(tasks_module, "AerSimulator", fake_aer_simulator)
    return fake_sim


@pytest.fixture
def patch_aer_failure(monkeypatch):
    class FakeSimulatorFail:
        def run(self, circuit, shots: int):  # noqa: D401
            raise RuntimeError("simulator failure")

    monkeypatch.setattr(tasks_module, "AerSimulator", lambda: FakeSimulatorFail())


# Tests --------------------------------------------------------------------------------------------------------------

def test_qasm3_task_success(valid_qasm3, patch_aer_success, patch_redis_client):
    task_id = "abc123"
    patch_redis_client.set(f"task_submitted:{task_id}", b"1")
    # Use small shots value for efficiency and verify propagation
    result = qasm3_fn(task_id, valid_qasm3, shots=8)
    assert result == {"00": 5, "11": 3}
    assert f"task_submitted:{task_id}" in patch_redis_client.deleted_keys
    assert patch_aer_success.last_shots == 8


def test_qasm3_task_parse_failure(patch_aer_success, patch_redis_client):
    task_id = "badparse"
    patch_redis_client.set(f"task_submitted:{task_id}", b"1")
    with pytest.raises(Exception):
        # Intentionally malformed QASM3 (missing declarations syntax etc.)
        qasm3_fn(task_id, "OPENQASM 3.0; qubit q[1] x q[0];", shots=4)
    assert f"task_submitted:{task_id}" not in patch_redis_client.deleted_keys


def test_qasm3_task_simulator_failure(valid_qasm3, patch_aer_failure, patch_redis_client):
    task_id = "simfail"
    patch_redis_client.set(f"task_submitted:{task_id}", b"1")
    with pytest.raises(RuntimeError):
        qasm3_fn(task_id, valid_qasm3, shots=4)
    assert f"task_submitted:{task_id}" not in patch_redis_client.deleted_keys


def test_qasm3_task_default_shots(valid_qasm3, patch_aer_success, patch_redis_client):
    task_id = "defaultshots"
    patch_redis_client.set(f"task_submitted:{task_id}", b"1")
    result = qasm3_fn(task_id, valid_qasm3)  # default shots
    assert result == {"00": 5, "11": 3}
    assert f"task_submitted:{task_id}" in patch_redis_client.deleted_keys


def test_qasm3_task_counts_is_new_dict(valid_qasm3, patch_aer_success, patch_redis_client):
    task_id = "copycheck"
    patch_redis_client.set(f"task_submitted:{task_id}", b"1")
    result = qasm3_fn(task_id, valid_qasm3)
    result["extra"] = 99
    second = qasm3_fn(task_id, valid_qasm3)
    assert "extra" not in second


from types import SimpleNamespace
import uuid
import pytest
from fastapi.testclient import TestClient

from app.api.v1.endpoints import experiments
from app.main import app


@pytest.fixture(autouse=True)
def clear_overrides():
    app.dependency_overrides = {}
    yield
    app.dependency_overrides = {}


def test_experiments_read_empty(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr(experiments, "experiment_service", SimpleNamespace(
        list_experiments=lambda db, skip=0, limit=100, sample_id=None: []
    ))
    app.dependency_overrides[experiments.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["viewer"], is_superuser=False
    )
    app.dependency_overrides[experiments.get_db] = lambda: iter([SimpleNamespace()])

    resp = client.get("/api/v1/experiments")
    assert resp.status_code == 200
    assert resp.json() == []


def test_experiments_get_prepared_payload_not_found(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr(experiments, "experiment_service", SimpleNamespace(
        get_experiment_prepared_payload=lambda db, experiment_id: None
    ))
    app.dependency_overrides[experiments.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )
    app.dependency_overrides[experiments.get_db] = lambda: iter([SimpleNamespace()])

    resp = client.get(f"/api/v1/experiments/{uuid.uuid4()}/prepared-payload")
    assert resp.status_code == 404


def test_experiments_read_by_id_not_found(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr(experiments, "experiment_service", SimpleNamespace(
        get=lambda db, experiment_id: None
    ))
    app.dependency_overrides[experiments.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["viewer"], is_superuser=False
    )
    app.dependency_overrides[experiments.get_db] = lambda: iter([SimpleNamespace()])

    resp = client.get(f"/api/v1/experiments/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_experiments_update_not_found(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr(experiments, "experiment_service", SimpleNamespace(
        update_experiment=lambda db, experiment_id, experiment_in: None
    ))
    app.dependency_overrides[experiments.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["curator"], is_superuser=False
    )
    app.dependency_overrides[experiments.get_db] = lambda: iter([SimpleNamespace()])

    resp = client.put(f"/api/v1/experiments/{uuid.uuid4()}", json={})
    assert resp.status_code == 404

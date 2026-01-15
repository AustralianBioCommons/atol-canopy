from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.v1.endpoints import assemblies
from app.main import app


class _FakeQueryList:
    def __init__(self, data):
        self.data = list(data)

    def filter(self, *_a, **_k):
        return self

    def all(self):
        return list(self.data)


class _FakeSession:
    def query(self, model):
        return _FakeQueryList([])


def _override_db(fake):
    def _gen():
        yield fake

    return _gen


def test_pipeline_inputs_no_samples_returns_empty_files(monkeypatch):
    client = TestClient(app)

    # Mock organism_service to return organism object
    organism = SimpleNamespace(grouping_key="g1", scientific_name="Sci", tax_id=1)
    monkeypatch.setattr(
        assemblies,
        "organism_service",
        SimpleNamespace(get_by_grouping_key=lambda db, key: organism),
    )

    # Active user
    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )
    app.dependency_overrides[assemblies.get_db] = _override_db(_FakeSession())

    resp = client.get("/api/v1/assemblies/pipeline-inputs?organism_grouping_key=g1")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list) and body
    assert body[0]["scientific_name"] == "Sci"
    assert body[0]["files"] == {}


def test_assemblies_pipeline_inputs_missing_param():
    client = TestClient(app)
    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )
    app.dependency_overrides[assemblies.get_db] = _override_db(_FakeSession())

    resp = client.get("/api/v1/assemblies/pipeline-inputs")
    assert resp.status_code == 422


def test_assemblies_pipeline_inputs_not_found(monkeypatch):
    client = TestClient(app)
    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )
    app.dependency_overrides[assemblies.get_db] = _override_db(_FakeSession())
    monkeypatch.setattr(
        assemblies.organism_service, "get_by_grouping_key", lambda db, grouping_key: None
    )

    resp = client.get("/api/v1/assemblies/pipeline-inputs?organism_grouping_key=missing")
    assert resp.status_code == 404

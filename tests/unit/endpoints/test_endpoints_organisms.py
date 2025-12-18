import uuid
from types import SimpleNamespace
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.api.v1.endpoints import organisms
from app.main import app


def _override_user():
    return SimpleNamespace(is_superuser=False, roles=["curator"], is_active=True)


class _FakeSession:
    def query(self, *_):
        return self


def _override_db(fake):
    def _gen():
        yield fake
    return _gen


def test_organisms_list_and_not_found(monkeypatch):
    client = TestClient(app)

    app.dependency_overrides[organisms.get_current_active_user] = _override_user
    app.dependency_overrides[organisms.get_db] = _override_db(_FakeSession())

    now = datetime.now(timezone.utc)
    base_org = {
        "grouping_key": "g1",
        "tax_id": 1,
        "scientific_name": "Sci",
        "common_name": "Com",
        "common_name_source": None,
        "bpa_json": None,
        "taxonomy_lineage_json": None,
        "created_at": now,
        "updated_at": now,
    }

    fake_service = SimpleNamespace(
        list_organisms=lambda db, skip=0, limit=100: [base_org],
        get_by_grouping_key=lambda db, grouping_key: None,
    )
    monkeypatch.setattr(organisms, "organism_service", fake_service)

    resp = client.get("/api/v1/organisms")
    assert resp.status_code == 200
    assert resp.json()[0]["grouping_key"] == "g1"

    resp = client.get("/api/v1/organisms/missing")
    assert resp.status_code == 404


def test_create_organism(monkeypatch):
    client = TestClient(app)

    app.dependency_overrides[organisms.get_current_active_user] = _override_user
    app.dependency_overrides[organisms.get_db] = _override_db(_FakeSession())

    now = datetime.now(timezone.utc)
    fake_service = SimpleNamespace(
        create_organism=lambda db, organism_in: {
            **organism_in.model_dump(),
            "grouping_key": "g1",
            "common_name_source": None,
            "bpa_json": None,
            "taxonomy_lineage_json": None,
            "created_at": now,
            "updated_at": now,
        }
    )
    monkeypatch.setattr(organisms, "organism_service", fake_service)
    monkeypatch.setattr(organisms, "require_role", lambda current_user, roles: None)

    payload = {
        "grouping_key": "g1",
        "tax_id": 1,
        "scientific_name": "Sci",
        "common_name": "Com",
    }

    resp = client.post("/api/v1/organisms", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["grouping_key"] == "g1"

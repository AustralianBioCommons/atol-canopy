import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.v1.endpoints import organisms
from app.main import app


def _override_user():
    return SimpleNamespace(is_superuser=False, roles=["curator"], is_active=True)


class _FakeSession:
    def __init__(self, organisms=None):
        self._organisms = organisms or []

    def query(self, *_):
        return self

    def offset(self, *_):
        return self

    def limit(self, *_):
        return self

    def all(self):
        return self._organisms

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return None


def _override_db(fake):
    def _gen():
        yield fake

    return _gen


def test_organisms_list_and_not_found(monkeypatch):
    client = TestClient(app)

    app.dependency_overrides[organisms.get_current_active_user] = _override_user

    now = datetime.now(timezone.utc)
    base_org = {
        "taxon_id": 1,
        "scientific_name": "Sci",
        "common_name": "Com",
        "common_name_source": None,
        "genus": None,
        "species": None,
        "infraspecific_epithet": None,
        "culture_or_strain_id": None,
        "authority": None,
        "atol_scientific_name": None,
        "tax_string": None,
        "ncbi_order": None,
        "ncbi_family": None,
        "busco_dataset_name": None,
        "bpa_json": None,
        "taxonomy_lineage_json": None,
        "taxonomy_info": None,
        "created_at": now,
        "updated_at": now,
    }

    app.dependency_overrides[organisms.get_db] = _override_db(_FakeSession([base_org]))
    monkeypatch.setattr(
        organisms,
        "organism_service",
        SimpleNamespace(get_by_taxon_id=lambda db, taxon_id: None),
    )

    resp = client.get("/api/v1/organisms")
    assert resp.status_code == 200
    assert resp.json()[0]["taxon_id"] == 1

    resp = client.get("/api/v1/organisms/999999")
    assert resp.status_code == 404


def test_create_organism(monkeypatch):
    client = TestClient(app)

    app.dependency_overrides[organisms.get_current_active_user] = _override_user
    app.dependency_overrides[organisms.get_db] = _override_db(_FakeSession())

    now = datetime.now(timezone.utc)
    fake_service = SimpleNamespace(
        create_organism=lambda db, organism_in: {
            **organism_in.model_dump(),
            "common_name_source": None,
            "bpa_json": None,
            "taxonomy_lineage_json": None,
            "created_at": now,
            "updated_at": now,
        }
    )
    monkeypatch.setattr(organisms, "organism_service", fake_service)
    payload = {
        "taxon_id": 1,
        "scientific_name": "Sci",
        "common_name": "Com",
    }

    resp = client.post("/api/v1/organisms", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["taxon_id"] == 1


def test_create_organism_without_scientific_name(monkeypatch):
    client = TestClient(app)

    app.dependency_overrides[organisms.get_current_active_user] = _override_user
    app.dependency_overrides[organisms.get_db] = _override_db(_FakeSession())

    now = datetime.now(timezone.utc)
    fake_service = SimpleNamespace(
        create_organism=lambda db, organism_in: {
            **organism_in.model_dump(),
            "common_name_source": None,
            "bpa_json": None,
            "taxonomy_lineage_json": None,
            "created_at": now,
            "updated_at": now,
        }
    )
    monkeypatch.setattr(organisms, "organism_service", fake_service)
    payload = {
        "taxon_id": 1,
        "common_name": "Com",
    }

    resp = client.post("/api/v1/organisms", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["taxon_id"] == 1
    assert body["scientific_name"] is None

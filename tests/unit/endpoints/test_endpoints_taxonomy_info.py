from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.v1.endpoints import taxonomy_info as ti_module
from app.main import app
from app.schemas.bulk_import import BulkImportResponse
from app.schemas.organism import Organism as OrganismSchema


def _override_user():
    return SimpleNamespace(is_superuser=False, roles=["curator"], is_active=True)


def _override_db(fake):
    def _gen():
        yield fake

    return _gen


def _make_ti(taxon_id=1, **kwargs):
    """Return a SimpleNamespace that looks like a TaxonomyInfo ORM object."""
    defaults = {
        "taxon_id": taxon_id,
        "busco_odb10_dataset_name": None,
        "busco_odb12_dataset_name": None,
        "find_plastid": None,
        "hic_motif": None,
        "mitochondrial_genetic_code_id": None,
        "oatk_hmm_name": None,
        "augustus_dataset_name": None,
        "genetic_code_id": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class _FakeSession:
    def query(self, *_):
        return self

    def offset(self, *_):
        return self

    def limit(self, *_):
        return self

    def all(self):
        return []

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return None


@pytest.fixture(autouse=True)
def _clear_overrides():
    app.dependency_overrides = {}
    yield
    app.dependency_overrides = {}


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


def test_list_taxonomy_info_empty(monkeypatch):
    client = TestClient(app)
    app.dependency_overrides[ti_module.get_current_active_user] = _override_user
    monkeypatch.setattr(
        ti_module,
        "taxonomy_info_service",
        SimpleNamespace(list=lambda db, skip=0, limit=100: []),
    )
    app.dependency_overrides[ti_module.get_db] = _override_db(_FakeSession())
    resp = client.get("/api/v1/taxonomy-info/")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_taxonomy_info_returns_records(monkeypatch):
    client = TestClient(app)
    app.dependency_overrides[ti_module.get_current_active_user] = _override_user
    ti = _make_ti(taxon_id=5077, augustus_dataset_name="anidulans", genetic_code_id=1)
    app.dependency_overrides[ti_module.get_db] = _override_db(_FakeSession())

    class _FakeSessionWithRow(_FakeSession):
        def all(self):
            return [ti]

    app.dependency_overrides[ti_module.get_db] = _override_db(_FakeSessionWithRow())
    resp = client.get("/api/v1/taxonomy-info/")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["taxon_id"] == 5077
    assert body[0]["augustus_dataset_name"] == "anidulans"


# ---------------------------------------------------------------------------
# Get by taxon_id
# ---------------------------------------------------------------------------


def test_get_taxonomy_info_found(monkeypatch):
    client = TestClient(app)
    app.dependency_overrides[ti_module.get_current_active_user] = _override_user
    app.dependency_overrides[ti_module.get_db] = _override_db(_FakeSession())
    ti = _make_ti(taxon_id=5077)
    monkeypatch.setattr(
        ti_module,
        "taxonomy_info_service",
        SimpleNamespace(get=lambda db, taxon_id: ti),
    )
    resp = client.get("/api/v1/taxonomy-info/5077")
    assert resp.status_code == 200
    assert resp.json()["taxon_id"] == 5077


def test_get_taxonomy_info_not_found(monkeypatch):
    client = TestClient(app)
    app.dependency_overrides[ti_module.get_current_active_user] = _override_user
    app.dependency_overrides[ti_module.get_db] = _override_db(_FakeSession())
    monkeypatch.setattr(
        ti_module,
        "taxonomy_info_service",
        SimpleNamespace(get=lambda db, taxon_id: None),
    )
    resp = client.get("/api/v1/taxonomy-info/9999")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


def test_create_taxonomy_info_success(monkeypatch):
    client = TestClient(app)
    app.dependency_overrides[ti_module.get_current_active_user] = _override_user
    app.dependency_overrides[ti_module.get_db] = _override_db(_FakeSession())
    ti = _make_ti(taxon_id=5077, augustus_dataset_name="anidulans")
    monkeypatch.setattr(
        ti_module,
        "taxonomy_info_service",
        SimpleNamespace(create=lambda db, ti_in: ti),
    )
    resp = client.post(
        "/api/v1/taxonomy-info/", json={"taxon_id": 5077, "augustus_dataset_name": "anidulans"}
    )
    assert resp.status_code == 201
    assert resp.json()["taxon_id"] == 5077


def test_create_taxonomy_info_organism_missing(monkeypatch):
    client = TestClient(app)
    app.dependency_overrides[ti_module.get_current_active_user] = _override_user
    app.dependency_overrides[ti_module.get_db] = _override_db(_FakeSession())

    def _raise(db, ti_in):
        raise ValueError("Organism with taxon_id 9999 does not exist")

    monkeypatch.setattr(
        ti_module,
        "taxonomy_info_service",
        SimpleNamespace(create=_raise),
    )
    resp = client.post("/api/v1/taxonomy-info/", json={"taxon_id": 9999})
    assert resp.status_code == 409
    assert "does not exist" in resp.json()["error"]["message"]


def test_create_taxonomy_info_duplicate(monkeypatch):
    client = TestClient(app)
    app.dependency_overrides[ti_module.get_current_active_user] = _override_user
    app.dependency_overrides[ti_module.get_db] = _override_db(_FakeSession())

    def _raise(db, ti_in):
        raise ValueError("TaxonomyInfo for taxon_id 5077 already exists")

    monkeypatch.setattr(
        ti_module,
        "taxonomy_info_service",
        SimpleNamespace(create=_raise),
    )
    resp = client.post("/api/v1/taxonomy-info/", json={"taxon_id": 5077})
    assert resp.status_code == 409
    assert "already exists" in resp.json()["error"]["message"]


def test_create_taxonomy_info_rejects_ncbi_fields():
    client = TestClient(app)
    app.dependency_overrides[ti_module.get_current_active_user] = _override_user
    app.dependency_overrides[ti_module.get_db] = _override_db(_FakeSession())
    resp = client.post(
        "/api/v1/taxonomy-info/",
        json={"taxon_id": 5077, "ncbi_rank": "species"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


def test_update_taxonomy_info_success(monkeypatch):
    client = TestClient(app)
    app.dependency_overrides[ti_module.get_current_active_user] = _override_user
    app.dependency_overrides[ti_module.get_db] = _override_db(_FakeSession())
    ti = _make_ti(taxon_id=5077, genetic_code_id=11)
    monkeypatch.setattr(
        ti_module,
        "taxonomy_info_service",
        SimpleNamespace(update=lambda db, taxon_id, ti_in: ti),
    )
    resp = client.patch("/api/v1/taxonomy-info/5077", json={"genetic_code_id": 11})
    assert resp.status_code == 200
    assert resp.json()["genetic_code_id"] == 11


def test_update_taxonomy_info_not_found(monkeypatch):
    client = TestClient(app)
    app.dependency_overrides[ti_module.get_current_active_user] = _override_user
    app.dependency_overrides[ti_module.get_db] = _override_db(_FakeSession())
    monkeypatch.setattr(
        ti_module,
        "taxonomy_info_service",
        SimpleNamespace(update=lambda db, taxon_id, ti_in: None),
    )
    resp = client.patch("/api/v1/taxonomy-info/9999", json={"genetic_code_id": 11})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


def _override_admin():
    return SimpleNamespace(is_superuser=False, roles=["admin"], is_active=True)


def test_delete_taxonomy_info_success(monkeypatch):
    client = TestClient(app)
    app.dependency_overrides[ti_module.get_current_active_user] = _override_admin
    app.dependency_overrides[ti_module.get_db] = _override_db(_FakeSession())
    ti = _make_ti(taxon_id=5077)
    monkeypatch.setattr(
        ti_module,
        "taxonomy_info_service",
        SimpleNamespace(delete=lambda db, taxon_id: ti),
    )
    resp = client.delete("/api/v1/taxonomy-info/5077")
    assert resp.status_code == 200
    assert resp.json()["taxon_id"] == 5077


def test_delete_taxonomy_info_not_found(monkeypatch):
    client = TestClient(app)
    app.dependency_overrides[ti_module.get_current_active_user] = _override_admin
    app.dependency_overrides[ti_module.get_db] = _override_db(_FakeSession())
    monkeypatch.setattr(
        ti_module,
        "taxonomy_info_service",
        SimpleNamespace(delete=lambda db, taxon_id: None),
    )
    resp = client.delete("/api/v1/taxonomy-info/9999")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Bulk import
# ---------------------------------------------------------------------------


def test_bulk_import_happy_path(monkeypatch):
    client = TestClient(app)
    app.dependency_overrides[ti_module.get_current_active_user] = _override_user
    app.dependency_overrides[ti_module.get_db] = _override_db(_FakeSession())
    result = BulkImportResponse(
        created_count=2,
        skipped_count=0,
        message="TaxonomyInfo import complete. Created: 2, Skipped: 0",
    )
    monkeypatch.setattr(
        ti_module,
        "taxonomy_info_service",
        SimpleNamespace(bulk_import=lambda db, data: result),
    )
    payload = {
        "5077": {"busco_odb12_dataset_name": "penicillium", "genetic_code_id": 1},
        "5303": {"busco_odb12_dataset_name": "agaricomycetes", "genetic_code_id": 1},
    }
    resp = client.post("/api/v1/taxonomy-info/bulk-import", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["created_count"] == 2
    assert body["skipped_count"] == 0


def test_bulk_import_skips_missing_organisms(monkeypatch):
    client = TestClient(app)
    app.dependency_overrides[ti_module.get_current_active_user] = _override_user
    app.dependency_overrides[ti_module.get_db] = _override_db(_FakeSession())
    result = BulkImportResponse(
        created_count=0,
        skipped_count=1,
        message="TaxonomyInfo import complete. Created: 0, Skipped: 1",
        errors=["9999: organism with taxon_id 9999 does not exist"],
    )
    monkeypatch.setattr(
        ti_module,
        "taxonomy_info_service",
        SimpleNamespace(bulk_import=lambda db, data: result),
    )
    resp = client.post("/api/v1/taxonomy-info/bulk-import", json={"9999": {}})
    assert resp.status_code == 200
    body = resp.json()
    assert body["skipped_count"] == 1
    assert any("does not exist" in e for e in body["errors"])


def test_bulk_import_skips_duplicates(monkeypatch):
    client = TestClient(app)
    app.dependency_overrides[ti_module.get_current_active_user] = _override_user
    app.dependency_overrides[ti_module.get_db] = _override_db(_FakeSession())
    result = BulkImportResponse(
        created_count=0,
        skipped_count=1,
        message="TaxonomyInfo import complete. Created: 0, Skipped: 1",
        errors=["5077: taxonomy_info for taxon_id 5077 already exists"],
    )
    monkeypatch.setattr(
        ti_module,
        "taxonomy_info_service",
        SimpleNamespace(bulk_import=lambda db, data: result),
    )
    resp = client.post("/api/v1/taxonomy-info/bulk-import", json={"5077": {}})
    assert resp.status_code == 200
    body = resp.json()
    assert body["skipped_count"] == 1
    assert any("already exists" in e for e in body["errors"])


def test_bulk_import_rejects_inner_taxon_id_field(monkeypatch):
    client = TestClient(app)
    app.dependency_overrides[ti_module.get_current_active_user] = _override_user
    app.dependency_overrides[ti_module.get_db] = _override_db(_FakeSession())
    resp = client.post("/api/v1/taxonomy-info/bulk-import", json={"5077": {"taxon_id": 9999}})
    assert resp.status_code == 422


def test_bulk_import_rejects_ncbi_fields():
    client = TestClient(app)
    app.dependency_overrides[ti_module.get_current_active_user] = _override_user
    app.dependency_overrides[ti_module.get_db] = _override_db(_FakeSession())
    resp = client.post("/api/v1/taxonomy-info/bulk-import", json={"5077": {"ncbi_rank": "species"}})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Schema-level assertions
# ---------------------------------------------------------------------------


def test_organism_schema_has_no_augustus_dataset_name():
    """OrganismSchema must not expose augustus_dataset_name at the top level."""
    fields = OrganismSchema.model_fields
    assert "augustus_dataset_name" not in fields


def test_organism_schema_has_taxonomy_info_field():
    """OrganismSchema must expose nested taxonomy_info."""
    fields = OrganismSchema.model_fields
    assert "taxonomy_info" in fields

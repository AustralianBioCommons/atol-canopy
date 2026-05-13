import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.v1.endpoints import bpa_initiatives
from app.main import app
from app.models.bpa_initiative import BPAInitiative


class FakeQueryList:
    def __init__(self, data):
        self.data = list(data)

    def filter(self, *args, **kwargs):
        return self

    def offset(self, *_):
        return self

    def limit(self, *_):
        return self

    def all(self):
        return list(self.data)

    def first(self):
        return self.data[0] if self.data else None


class FakeSessionMap:
    def __init__(self, data_map=None):
        self.data_map = data_map or {}
        self.added = []

    def query(self, model):
        return FakeQueryList(self.data_map.get(model, []))

    def add(self, obj):
        self.added.append(obj)
        self.data_map.setdefault(type(obj), []).append(obj)

    def commit(self):
        pass

    def refresh(self, obj):
        now = datetime.now(timezone.utc)
        if getattr(obj, "created_at", None) is None:
            obj.created_at = now
        if getattr(obj, "updated_at", None) is None:
            obj.updated_at = now


def override_db(data=None):
    def _gen():
        yield FakeSessionMap(data)

    return _gen


def override_fake_db(fake):
    def _gen():
        yield fake

    return _gen


def test_bpa_initiatives_list_empty():
    client = TestClient(app)
    app.dependency_overrides[bpa_initiatives.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )
    app.dependency_overrides[bpa_initiatives.get_db] = override_db({})

    resp = client.get("/api/v1/bpa-initiatives")
    assert resp.status_code == 200
    assert resp.json() == []


def test_bpa_initiative_not_found():
    client = TestClient(app)
    app.dependency_overrides[bpa_initiatives.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )
    app.dependency_overrides[bpa_initiatives.get_db] = override_db({})

    resp = client.get(f"/api/v1/bpa-initiatives/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_create_bpa_initiative_uses_current_model_shape():
    client = TestClient(app)
    fake_db = FakeSessionMap({})
    app.dependency_overrides[bpa_initiatives.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )
    app.dependency_overrides[bpa_initiatives.get_db] = override_fake_db(fake_db)

    resp = client.post(
        "/api/v1/bpa-initiatives",
        json={
            "project_code": "atol-demo",
            "title": "AToL Demo Initiative",
            "url": "https://example.org/initiative",
        },
    )

    assert resp.status_code == 200
    assert resp.json()["project_code"] == "atol-demo"
    assert resp.json()["title"] == "AToL Demo Initiative"
    assert resp.json()["url"] == "https://example.org/initiative"


def test_read_bpa_initiative_serializes_current_fields():
    client = TestClient(app)
    initiative = BPAInitiative(
        project_code="atol-demo",
        title="AToL Demo Initiative",
        url="https://example.org/initiative",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    app.dependency_overrides[bpa_initiatives.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )
    app.dependency_overrides[bpa_initiatives.get_db] = override_db({BPAInitiative: [initiative]})

    resp = client.get("/api/v1/bpa-initiatives/atol-demo")

    assert resp.status_code == 200
    assert resp.json()["project_code"] == "atol-demo"
    assert resp.json()["title"] == "AToL Demo Initiative"

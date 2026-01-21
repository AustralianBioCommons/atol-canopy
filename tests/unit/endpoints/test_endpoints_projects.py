import uuid
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.v1.endpoints import projects
from app.main import app


class FakeQueryList:
    def __init__(self, data):
        self.data = list(data)

    def offset(self, *_):
        return self

    def limit(self, *_):
        return self

    def all(self):
        return list(self.data)

    def filter(self, *_a, **_k):
        return self

    def first(self):
        return self.data[0] if self.data else None


class FakeSessionMap:
    def __init__(self, data_map=None):
        self.data_map = data_map or {}

    def query(self, model):
        return FakeQueryList(self.data_map.get(model, []))


def override_db(data=None):
    def _gen():
        yield FakeSessionMap(data)

    return _gen


def test_projects_list_empty():
    client = TestClient(app)
    app.dependency_overrides[projects.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )
    app.dependency_overrides[projects.get_db] = override_db({})

    resp = client.get("/api/v1/projects")
    assert resp.status_code == 200
    assert resp.json() == []


def test_project_not_found():
    client = TestClient(app)
    app.dependency_overrides[projects.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )
    app.dependency_overrides[projects.get_db] = override_db({})

    resp = client.get(f"/api/v1/projects/{uuid.uuid4()}")
    assert resp.status_code == 404

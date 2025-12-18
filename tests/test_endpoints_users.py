import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.v1.endpoints import users
from app.main import app


@pytest.fixture(autouse=True)
def _jwt_settings(monkeypatch):
    # Ensure predictable JWT config
    from app.core.settings import settings
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "test-secret")
    monkeypatch.setattr(settings, "JWT_ALGORITHM", "HS256")
    monkeypatch.setattr(settings, "JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 30)


class _FakeCreateSession:
    """Fake session for create_user that returns successive results for first() calls."""
    def __init__(self, first_results):
        self._iter = iter(first_results)
        self.added = []
        self.committed = False

    def query(self, model):
        return self

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return next(self._iter, None)

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.committed = True

    def refresh(self, obj):
        pass


def _override_db(fake):
    def _gen():
        yield fake
    return _gen


def test_users_create_duplicate_username():
    client = TestClient(app)
    existing = SimpleNamespace(id=uuid.uuid4(), username="taken")
    app.dependency_overrides[users.get_db] = _override_db(_FakeCreateSession([existing]))

    payload = {
        "username": "taken",
        "email": "a@example.org",
        "password": "goodpass",
        "full_name": "A",
        "roles": [],
        "is_active": True,
    }
    resp = client.post("/api/v1/users/", json=payload)
    assert resp.status_code == 400


def test_users_create_duplicate_email():
    client = TestClient(app)
    existing = SimpleNamespace(id=uuid.uuid4(), email="a@example.org")
    # First query (username) -> None, second (email) -> existing
    app.dependency_overrides[users.get_db] = _override_db(_FakeCreateSession([None, existing]))

    payload = {
        "username": "newuser",
        "email": "a@example.org",
        "password": "goodpass",
        "full_name": "A",
        "roles": [],
        "is_active": True,
    }
    resp = client.post("/api/v1/users/", json=payload)
    assert resp.status_code == 400


def test_users_create_success(monkeypatch):
    client = TestClient(app)
    fake = _FakeCreateSession([None, None])
    app.dependency_overrides[users.get_db] = _override_db(fake)

    payload = {
        "username": "newuser",
        "email": "new@example.org",
        "password": "goodpass",
        "full_name": "A",
        "roles": ["viewer"],
        "is_active": True,
    }
    resp = client.post("/api/v1/users/", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["username"] == "newuser"
    assert body["email"] == "new@example.org"


class _ListQuery:
    def __init__(self, items):
        self.items = items

    def offset(self, *_):
        return self

    def limit(self, *_):
        return self

    def all(self):
        return list(self.items)


class _ListSession:
    def __init__(self, items):
        self.items = items

    def query(self, model):
        return _ListQuery(self.items)


def test_users_list_empty():
    client = TestClient(app)
    app.dependency_overrides[users.get_db] = _override_db(_ListSession([]))
    resp = client.get("/api/v1/users/")
    assert resp.status_code == 200
    assert resp.json() == []


class _UpdateSession:
    def __init__(self):
        self.committed = False

    def add(self, obj):
        pass

    def commit(self):
        self.committed = True

    def refresh(self, obj):
        pass


def test_users_update_me_success(monkeypatch):
    client = TestClient(app)

    current = SimpleNamespace(id=uuid.uuid4(), username="u", email="e@example.org", full_name=None, hashed_password="x", is_active=True)

    def override_user():
        return current

    app.dependency_overrides[users.get_current_active_user] = override_user
    app.dependency_overrides[users.get_db] = _override_db(_UpdateSession())

    resp = client.put("/api/v1/users/me", json={"username": "u2", "email": "e2@example.org", "password": "newpass"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["username"] == "u2"
    assert body["email"] == "e2@example.org"


def test_users_update_not_found():
    client = TestClient(app)

    class _QueryNone:
        def filter(self, *_a, **_k):
            return self
        def first(self):
            return None

    class _SessionNone:
        def query(self, _m):
            return _QueryNone()

    app.dependency_overrides[users.get_db] = _override_db(_SessionNone())

    resp = client.put(f"/api/v1/users/{uuid.uuid4()}", json={"username": "x"})
    assert resp.status_code == 404


def test_users_read_by_id_success():
    client = TestClient(app)

    user_id = uuid.uuid4()
    expected = SimpleNamespace(id=user_id, username="u", email="e@example.org", full_name=None, roles=[], is_active=True)

    class _QueryOne:
        def __init__(self, obj):
            self.obj = obj
        def filter(self, *_a, **_k):
            return self
        def first(self):
            return self.obj

    class _SessionOne:
        def query(self, _m):
            return _QueryOne(expected)

    app.dependency_overrides[users.get_db] = _override_db(_SessionOne())

    resp = client.get(f"/api/v1/users/{user_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(user_id)

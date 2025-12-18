import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.settings import settings
from app.core.security import hash_token
from app.api.v1.endpoints import auth
from app.main import app


@pytest.fixture(autouse=True)
def _jwt_settings(monkeypatch):
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "test-secret")
    monkeypatch.setattr(settings, "JWT_ALGORITHM", "HS256")
    monkeypatch.setattr(settings, "JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 30)
    monkeypatch.setattr(settings, "JWT_REFRESH_TOKEN_EXPIRE_DAYS", 7)


@pytest.fixture(autouse=True)
def clear_overrides():
    app.dependency_overrides = {}
    yield
    app.dependency_overrides = {}


class FakeQuery:
    def __init__(self, result=None):
        self._result = result
        self.updated = False

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._result

    def update(self, *_args, **_kwargs):
        self.updated = True
        return 1


class FakeSession:
    def __init__(self, refresh_token=None, user=None):
        self._refresh_token = refresh_token
        self._user = user
        self.committed = False
        self.query_refresh_updated = False

    def query(self, model):
        name = getattr(model, "__name__", "")
        if name == "RefreshToken":
            q = FakeQuery(self._refresh_token)
            def _update(set_map):
                self.query_refresh_updated = True
                return 1
            q.update = _update  # type: ignore[attr-defined]
            return q
        if name == "User":
            return FakeQuery(self._user)
        return FakeQuery(None)

    def add(self, obj):
        pass

    def commit(self):
        self.committed = True

    def close(self):
        pass


def test_login_inactive_user(monkeypatch):
    client = TestClient(app)

    inactive = SimpleNamespace(id=uuid.uuid4(), is_active=False)
    monkeypatch.setattr(auth, "authenticate_user", lambda db, username, password: inactive)

    def override_db():
        yield FakeSession()
    app.dependency_overrides[auth.get_db] = override_db

    resp = client.post("/api/v1/auth/login", data={"username": "u", "password": "p"})
    assert resp.status_code == 400


def test_refresh_invalid_token():
    client = TestClient(app)

    def override_db():
        yield FakeSession(refresh_token=None)
    app.dependency_overrides[auth.get_db] = override_db

    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": "bad"})
    assert resp.status_code == 401


def test_refresh_user_inactive_revokes(monkeypatch):
    client = TestClient(app)

    rt = SimpleNamespace(token_hash="h", user_id=uuid.uuid4(), expires_at=None, revoked=False)
    # Return inactive user
    inactive_user = SimpleNamespace(id=rt.user_id, is_active=False)

    def override_db():
        yield FakeSession(refresh_token=rt, user=inactive_user)
    app.dependency_overrides[auth.get_db] = override_db

    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": "value"})
    assert resp.status_code == 401
    assert rt.revoked is True


def test_logout_revokes_all(monkeypatch):
    client = TestClient(app)

    user = SimpleNamespace(id=uuid.uuid4())

    def override_user():
        return user

    fake_db = FakeSession()

    def override_db():
        yield fake_db

    app.dependency_overrides[auth.get_db] = override_db
    app.dependency_overrides[auth.get_current_user] = override_user

    resp = client.post("/api/v1/auth/logout")
    assert resp.status_code == 200
    assert fake_db.committed is True


def test_login_success(monkeypatch):
    client = TestClient(app)

    fake_user = SimpleNamespace(
        id=uuid.uuid4(),
        is_active=True,
        is_superuser=False,
        roles=[],
    )

    class _LoginFakeSession:
        def __init__(self):
            self.added = []
            self.committed = False
        def query(self, *_):
            return SimpleNamespace(filter=lambda *a, **k: self, first=lambda: None)
        def add(self, obj):
            self.added.append(obj)
        def commit(self):
            self.committed = True

    fake_db = _LoginFakeSession()

    def override_db():
        yield fake_db

    monkeypatch.setattr(auth, "authenticate_user", lambda db, username, password: fake_user)
    app.dependency_overrides[auth.get_db] = override_db

    resp = client.post(
        "/api/v1/auth/login",
        data={"username": "user", "password": "pass"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data and "refresh_token" in data


def test_login_invalid_credentials(monkeypatch):
    client = TestClient(app)

    def override_db():
        yield SimpleNamespace()
    app.dependency_overrides[auth.get_db] = override_db

    monkeypatch.setattr(auth, "authenticate_user", lambda db, username, password: None)

    resp = client.post(
        "/api/v1/auth/login",
        data={"username": "user", "password": "wrong"},
    )
    assert resp.status_code == 401


def test_refresh_token_success(monkeypatch):
    client = TestClient(app)

    user = SimpleNamespace(
        id=uuid.uuid4(),
        is_active=True,
        is_superuser=False,
        roles=[],
    )
    refresh_token_value = "refresh-token"
    stored_token = SimpleNamespace(
        token_hash=hash_token(refresh_token_value),
        expires_at=None,
        revoked=False,
        user_id=user.id,
    )

    class _RefreshSession:
        def __init__(self):
            self._refresh = stored_token
            self._user = user
            self.committed = False
        def query(self, model):
            name = getattr(model, "__name__", "")
            class _Q:
                def __init__(self, first_val):
                    self._first_val = first_val
                def filter(self, *a, **k):
                    return self
                def first(self):
                    return self._first_val
                def update(self, *_a, **_k):
                    return 1
            if name == "RefreshToken":
                return _Q(self._refresh)
            if name == "User":
                return _Q(self._user)
            return _Q(None)
        def add(self, obj):
            pass
        def commit(self):
            self.committed = True

    fake_db = _RefreshSession()

    def override_db():
        yield fake_db

    app.dependency_overrides[auth.get_db] = override_db

    resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token_value},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data and "refresh_token" in data

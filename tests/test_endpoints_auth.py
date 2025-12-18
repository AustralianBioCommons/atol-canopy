import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.settings import settings
from app.api.v1.endpoints import auth
from app.main import app


@pytest.fixture(autouse=True)
def _jwt_settings(monkeypatch):
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "test-secret")
    monkeypatch.setattr(settings, "JWT_ALGORITHM", "HS256")
    monkeypatch.setattr(settings, "JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 30)
    monkeypatch.setattr(settings, "JWT_REFRESH_TOKEN_EXPIRE_DAYS", 7)


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

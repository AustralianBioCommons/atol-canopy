import types
import uuid
import pytest
from fastapi import HTTPException
from jose import jwt

from app.core import dependencies
from app.core.settings import settings
from app.models.user import User  # only used for attribute reference in FakeSession


class FakeQuery:
    def __init__(self, result):
        self.result = result

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self.result


class FakeSession:
    def __init__(self, user=None):
        self._user = user

    def query(self, model):
        if model is User:
            return FakeQuery(self._user)
        return FakeQuery(None)


@pytest.fixture(autouse=True)
def jwt_settings(monkeypatch):
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "test-secret")
    monkeypatch.setattr(settings, "JWT_ALGORITHM", "HS256")
    monkeypatch.setattr(settings, "JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 30)


def test_get_current_user_invalid_token():
    fake_db = FakeSession()
    with pytest.raises(HTTPException) as exc:
        dependencies.get_current_user(db=fake_db, token="invalid.jwt.token")
    assert exc.value.status_code == 401


def test_get_current_user_missing_sub():
    # token without 'sub'
    token = jwt.encode({"foo": "bar"}, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    fake_db = FakeSession()
    with pytest.raises(HTTPException) as exc:
        dependencies.get_current_user(db=fake_db, token=token)
    assert exc.value.status_code == 401


def test_get_current_user_inactive_user():
    user_id = str(uuid.uuid4())
    token = jwt.encode({"sub": user_id}, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    # inactive user object
    inactive = types.SimpleNamespace(id=user_id, is_active=False)
    fake_db = FakeSession(user=inactive)
    with pytest.raises(HTTPException) as exc:
        dependencies.get_current_user(db=fake_db, token=token)
    assert exc.value.status_code == 400


def test_has_role_allows_superuser():
    fn = dependencies.has_role(["admin"])  # returns callable
    superuser = types.SimpleNamespace(is_superuser=True, roles=["anything"])
    got = fn(superuser)
    assert got is superuser


def test_has_role_forbidden_when_missing():
    fn = dependencies.has_role(["curator"])  # returns callable
    user = types.SimpleNamespace(is_superuser=False, roles=["viewer"])  # missing role
    with pytest.raises(HTTPException) as exc:
        fn(user)
    assert exc.value.status_code == 403

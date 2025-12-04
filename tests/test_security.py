from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt
from passlib.context import CryptContext

from app.core import security
from app.core.settings import settings


@pytest.fixture(autouse=True)
def _mock_jwt_settings(monkeypatch):
    """Ensure JWT settings are present for security helpers."""
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "test-secret")
    monkeypatch.setattr(settings, "JWT_ALGORITHM", "HS256")
    monkeypatch.setattr(settings, "JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 30)
    monkeypatch.setattr(
        security,
        "pwd_context",
        CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto"),
    )


def test_create_access_token_uses_defaults():
    start = datetime.now(timezone.utc)

    token = security.create_access_token("user-123")
    payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])

    assert payload["sub"] == "user-123"
    exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    assert start < exp < start + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES, seconds=5)


def test_create_access_token_accepts_custom_expiry():
    start = datetime.now(timezone.utc)
    expires = timedelta(seconds=2)

    token = security.create_access_token("custom", expires_delta=expires)
    payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])

    exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    assert start < exp < start + expires + timedelta(seconds=1)


def test_password_hash_round_trip():
    hashed = security.get_password_hash("s3cr3t!")

    assert security.verify_password("s3cr3t!", hashed)
    assert not security.verify_password("wrong", hashed)


def test_generate_and_hash_tokens_are_safe_and_deterministic():
    token_a = security.generate_refresh_token(length=16)
    token_b = security.generate_refresh_token(length=16)

    assert token_a != token_b
    assert len(token_a) >= 16
    assert len(token_b) >= 16

    hashed_a1 = security.hash_token(token_a)
    hashed_a2 = security.hash_token(token_a)
    hashed_b = security.hash_token(token_b)

    assert hashed_a1 == hashed_a2
    assert hashed_a1 != hashed_b

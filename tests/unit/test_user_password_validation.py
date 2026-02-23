from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.v1.endpoints import users
from app.main import app


def _override_admin_user():
    return {"is_superuser": False, "roles": ["admin"], "is_active": True}


def test_create_user_rejects_password_over_72_bytes():
    client = TestClient(app)
    app.dependency_overrides[users.get_current_active_user] = _override_admin_user

    payload = {
        "username": "u1",
        "email": "u1@example.org",
        "full_name": "User One",
        "roles": [],
        "is_active": True,
        # 80 ASCII chars => 80 bytes in UTF-8
        "password": "a" * 80,
    }

    resp = client.post("/api/v1/users/", json=payload)
    assert resp.status_code == 422

    detail = resp.json().get("error", {}).get("details", {}).get("errors")
    assert isinstance(detail, list)
    # Ensure we fail due to our validator message
    assert any("at most 72 bytes" in (err.get("msg") or "") for err in detail)


def test_update_user_rejects_password_over_72_bytes():
    client = TestClient(app)
    app.dependency_overrides[users.get_current_active_user] = _override_admin_user

    user_id = str(uuid4())
    payload = {
        # Only updating password; other fields optional
        "password": "b" * 80,  # 80 bytes
    }

    resp = client.put(f"/api/v1/users/{user_id}", json=payload)
    assert resp.status_code == 422

    detail = resp.json().get("error", {}).get("details", {}).get("errors")
    assert isinstance(detail, list)
    assert any("at most 72 bytes" in (err.get("msg") or "") for err in detail)

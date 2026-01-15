from fastapi.testclient import TestClient

from app.main import app


def test_root_endpoint():
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert "message" in body and "docs" in body

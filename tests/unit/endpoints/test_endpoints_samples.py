import uuid
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.v1.endpoints import samples
from app.main import app


class _FakeSession:
    def query(self, *_):
        return self

    def filter(self, *_a, **_k):
        return self

    def first(self):
        return None


def _override_db(fake):
    def _gen():
        yield fake

    return _gen


def test_sample_not_found():
    client = TestClient(app)
    app.dependency_overrides[samples.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )
    app.dependency_overrides[samples.get_db] = _override_db(_FakeSession())

    resp = client.get(f"/api/v1/samples/{uuid.uuid4()}")
    assert resp.status_code == 404

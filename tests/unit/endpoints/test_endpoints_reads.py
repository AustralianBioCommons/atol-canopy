import uuid
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.v1.endpoints import reads
from app.main import app


def _override_db(fake):
    def _gen():
        yield fake

    return _gen


def test_read_not_found():
    client = TestClient(app)
    app.dependency_overrides[reads.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )

    class _QueryNone:
        def filter(self, *_a, **_k):
            return self

        def first(self):
            return None

    class _SessionNone:
        def query(self, _m):
            return _QueryNone()

    app.dependency_overrides[reads.get_db] = _override_db(_SessionNone())

    resp = client.get(f"/api/v1/reads/{uuid.uuid4()}")
    assert resp.status_code == 404

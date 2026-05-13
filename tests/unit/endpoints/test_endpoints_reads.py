import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.v1.endpoints import reads
from app.main import app
from app.models.read import Read


def _override_db(fake):
    def _gen():
        yield fake

    return _gen


class _QuerySingle:
    def __init__(self, obj):
        self.obj = obj

    def filter(self, *_a, **_k):
        return self

    def first(self):
        return self.obj


class _SessionSingle:
    def __init__(self, read_obj=None):
        self.read_obj = read_obj

    def query(self, _model):
        return _QuerySingle(self.read_obj)

    def add(self, obj):
        self.read_obj = obj

    def commit(self):
        pass

    def refresh(self, obj):
        now = datetime.now(timezone.utc)
        if getattr(obj, "created_at", None) is None:
            obj.created_at = now
        if getattr(obj, "updated_at", None) is None:
            obj.updated_at = now


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


def test_create_read_returns_current_model_fields():
    client = TestClient(app)
    fake_db = _SessionSingle()
    app.dependency_overrides[reads.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )
    app.dependency_overrides[reads.get_db] = _override_db(fake_db)

    resp = client.post(
        "/api/v1/reads",
        json={
            "experiment_id": str(uuid.uuid4()),
            "bpa_resource_id": "res-1",
            "bpa_dataset_id": "dataset-1",
            "file_name": "reads.fastq.gz",
            "file_checksum": "abc123",
            "file_format": "fastq",
            "optional_file": False,
            "bioplatforms_url": "https://example.org/read",
            "read_number": "1",
            "lane_number": "L001",
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["bpa_dataset_id"] == "dataset-1"
    assert body["file_name"] == "reads.fastq.gz"
    assert body["optional_file"] is False


def test_update_read_ignores_dead_fields_and_updates_real_columns():
    client = TestClient(app)
    read_obj = Read(
        id=uuid.uuid4(),
        experiment_id=uuid.uuid4(),
        bpa_resource_id="res-1",
        bpa_dataset_id="dataset-1",
        file_name="reads.fastq.gz",
        file_checksum="abc123",
        file_format="fastq",
        optional_file=True,
        read_number="1",
        lane_number="L001",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    fake_db = _SessionSingle(read_obj)
    app.dependency_overrides[reads.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )
    app.dependency_overrides[reads.get_db] = _override_db(fake_db)

    resp = client.put(
        f"/api/v1/reads/{read_obj.id}",
        json={"bpa_dataset_id": "dataset-2", "run_read_count": "999"},
    )

    assert resp.status_code == 200
    assert resp.json()["bpa_dataset_id"] == "dataset-2"
    assert read_obj.bpa_dataset_id == "dataset-2"
    assert not hasattr(read_obj, "run_read_count")

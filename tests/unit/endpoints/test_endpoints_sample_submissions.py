import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.v1.endpoints import sample_submissions
from app.main import app
from app.models.project import Project
from app.models.sample import SampleSubmission


def _override_db(fake):
    def _gen():
        yield fake

    return _gen


class _Query:
    def __init__(self, obj):
        self.obj = obj

    def filter(self, *_a, **_k):
        return self

    def first(self):
        return self.obj

    def all(self):
        return [self.obj] if self.obj is not None else []

    def offset(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self


class _Session:
    def __init__(self, sample_obj, project_obj):
        self.sample_obj = sample_obj
        self.project_obj = project_obj
        self.submission_obj = None

    def query(self, model):
        if model is SampleSubmission:
            return _Query(self.submission_obj)
        if model is Project:
            return _Query(self.project_obj)
        return _Query(self.sample_obj)

    def add(self, obj):
        self.submission_obj = obj

    def commit(self):
        pass

    def refresh(self, obj):
        now = datetime.now(timezone.utc)
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        if getattr(obj, "created_at", None) is None:
            obj.created_at = now
        if getattr(obj, "updated_at", None) is None:
            obj.updated_at = now


def test_create_sample_submission_derives_project_id():
    client = TestClient(app)
    sample_id = uuid.uuid4()
    project_id = uuid.uuid4()
    fake_db = _Session(
        sample_obj=SimpleNamespace(id=sample_id, taxon_id=172942),
        project_obj=SimpleNamespace(id=project_id, taxon_id=172942, project_type="genomic_data"),
    )

    app.dependency_overrides[sample_submissions.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["curator"], is_superuser=False
    )
    app.dependency_overrides[sample_submissions.get_db] = _override_db(fake_db)

    resp = client.post(
        "/api/v1/sample-submissions",
        json={
            "sample_id": str(sample_id),
            "authority": "ENA",
            "status": "draft",
            "entity_type_const": "sample",
            "prepared_payload": {"title": "sample"},
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["sample_id"] == str(sample_id)
    assert body["project_id"] == str(project_id)
    assert body["prepared_payload"] == {"title": "sample"}

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.v1.endpoints import projects
from app.main import app
from app.schemas.project import ProjectCreate, ProjectUpdate


class FakeQueryList:
    def __init__(self, data):
        self.data = list(data)

    def offset(self, *_):
        return self

    def limit(self, *_):
        return self

    def all(self):
        return list(self.data)

    def filter(self, *_a, **_k):
        return self

    def first(self):
        return self.data[0] if self.data else None


class FakeSessionMap:
    def __init__(self, data_map=None):
        self.data_map = data_map or {}

    def query(self, model):
        return FakeQueryList(self.data_map.get(model, []))


def override_db(data=None):
    def _gen():
        yield FakeSessionMap(data)

    return _gen


def test_projects_list_empty():
    client = TestClient(app)
    app.dependency_overrides[projects.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )
    app.dependency_overrides[projects.get_db] = override_db({})

    resp = client.get("/api/v1/projects")
    assert resp.status_code == 200
    assert resp.json() == []


def test_project_not_found():
    client = TestClient(app)
    app.dependency_overrides[projects.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )
    app.dependency_overrides[projects.get_db] = override_db({})

    resp = client.get(f"/api/v1/projects/{uuid.uuid4()}")
    assert resp.status_code == 404


class _ProjectMutationSession:
    def __init__(self, existing=None):
        self.existing = existing
        self.added = []
        self.committed = False

    def query(self, _model):
        return FakeQueryList([self.existing] if self.existing else [])

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.committed = True

    def refresh(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        if getattr(obj, "created_at", None) is None:
            obj.created_at = datetime.now(timezone.utc)
        if getattr(obj, "updated_at", None) is None:
            obj.updated_at = datetime.now(timezone.utc)


def test_create_project_uses_current_project_model():
    db = _ProjectMutationSession()
    project_in = ProjectCreate(
        taxon_id=1729,
        project_type="genomic_data",
        project_accession=None,
        study_type="Whole Genome Sequencing",
        alias="proj-alias",
        title="Project title",
        description="Project description",
    )

    out = projects.create_project(
        db=db,
        project_in=project_in,
        current_user=SimpleNamespace(is_active=True, roles=["admin"], is_superuser=False),
    )

    assert out.project_type == "genomic_data"
    assert out.study_type == "Whole Genome Sequencing"
    assert out.title == "Project title"
    assert db.committed is True


def test_update_project_mutates_model_fields():
    existing = SimpleNamespace(
        id=uuid.uuid4(),
        taxon_id=1729,
        project_type="genomic_data",
        project_accession=None,
        study_type="Whole Genome Sequencing",
        alias="old",
        title="Old title",
        description="Old description",
        centre_name="AToL",
        study_attributes=None,
        submitted_at=None,
        status="draft",
        authority="ENA",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db = _ProjectMutationSession(existing)

    out = projects.update_project(
        db=db,
        project_id=existing.id,
        project_in=ProjectUpdate(title="New title", description="New description"),
        current_user=SimpleNamespace(is_active=True, roles=["admin"], is_superuser=False),
    )

    assert out.title == "New title"
    assert out.description == "New description"

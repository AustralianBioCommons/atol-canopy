import os
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException

# Ensure settings have usable DB values before importing the app (engine creation is lazy)
os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("POSTGRES_SERVER", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ.setdefault("POSTGRES_DB", "testdb")

from app.main import app
from app.api.v1.endpoints import auth
from app.api.v1.endpoints import organisms
from app.api.v1.endpoints import assemblies, experiment_reads_xml, experiment_submissions, genome_notes, reads, samples, users, xml_export, broker
from app.core.security import hash_token
from app.core.settings import settings


class FakeQuery:
    def __init__(self, result):
        self.result = result

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.result


class FakeSession:
    def __init__(self, refresh_token=None, user=None):
        self._refresh_token = refresh_token
        self._user = user
        self.added = []
        self.committed = False

    def query(self, model):
        name = getattr(model, "__name__", "")
        if name == "RefreshToken":
            return FakeQuery(self._refresh_token)
        if name == "User":
            return FakeQuery(self._user)
        return FakeQuery(None)

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.committed = True

    def close(self):
        pass


class FakeQueryList:
    def __init__(self, data):
        self.data = list(data)

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def distinct(self, *args, **kwargs):
        return self

    def offset(self, *_):
        return self

    def limit(self, *_):
        return self

    def all(self):
        return list(self.data)

    def first(self):
        return self.data[0] if self.data else None


class FakeSessionMap:
    def __init__(self, data_map=None):
        self.data_map = data_map or {}

    def query(self, model):
        return FakeQueryList(self.data_map.get(model, []))

    def add(self, obj):
        pass

    def commit(self):
        pass

    def refresh(self, obj):
        pass

    def close(self):
        pass


def override_db_map(data=None):
    def _gen():
        yield FakeSessionMap(data)
    return _gen


@pytest.fixture(autouse=True)
def _jwt_settings(monkeypatch):
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "test-secret")
    monkeypatch.setattr(settings, "JWT_ALGORITHM", "HS256")
    monkeypatch.setattr(settings, "JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 30)
    monkeypatch.setattr(settings, "JWT_REFRESH_TOKEN_EXPIRE_DAYS", 7)


@pytest.fixture(autouse=True)
def clear_overrides():
    app.dependency_overrides = {}
    yield
    app.dependency_overrides = {}


def test_root_endpoint():
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert "message" in body and "docs" in body


def test_login_success(monkeypatch):
    client = TestClient(app)

    fake_user = SimpleNamespace(
        id=uuid.uuid4(),
        is_active=True,
        is_superuser=False,
        roles=[],
    )

    fake_db = FakeSession()

    def override_db():
        yield fake_db

    monkeypatch.setattr(auth, "authenticate_user", lambda db, username, password: fake_user)
    app.dependency_overrides[auth.get_db] = override_db

    resp = client.post(
        "/api/v1/auth/login",
        data={"username": "user", "password": "pass"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data and "refresh_token" in data
    # Refresh token persisted through fake DB
    assert fake_db.added and fake_db.committed


def test_login_invalid_credentials(monkeypatch):
    client = TestClient(app)

    def override_db():
        yield FakeSession()

    monkeypatch.setattr(auth, "authenticate_user", lambda db, username, password: None)
    app.dependency_overrides[auth.get_db] = override_db

    resp = client.post(
        "/api/v1/auth/login",
        data={"username": "user", "password": "wrong"},
    )

    assert resp.status_code == 401


def test_refresh_token_success(monkeypatch):
    client = TestClient(app)

    user = SimpleNamespace(
        id=uuid.uuid4(),
        is_active=True,
        is_superuser=False,
        roles=[],
    )
    refresh_token_value = "refresh-token"
    stored_token = SimpleNamespace(
        token_hash=hash_token(refresh_token_value),
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        revoked=False,
        user_id=user.id,
    )

    fake_db = FakeSession(refresh_token=stored_token, user=user)

    def override_db():
        yield fake_db

    app.dependency_overrides[auth.get_db] = override_db

    resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token_value},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data and "refresh_token" in data


def test_organisms_list_and_not_found(monkeypatch):
    client = TestClient(app)
    user = SimpleNamespace(is_superuser=False, roles=["curator"], is_active=True)

    def override_user():
        return user

    def override_db():
        yield FakeSession()

    now = datetime.now(timezone.utc)
    base_org = {
        "grouping_key": "g1",
        "tax_id": 1,
        "scientific_name": "Sci",
        "common_name": "Com",
        "common_name_source": None,
        "bpa_json": None,
        "taxonomy_lineage_json": None,
        "created_at": now,
        "updated_at": now,
    }

    fake_service = SimpleNamespace(
        list_organisms=lambda db, skip=0, limit=100: [base_org],
        get_by_grouping_key=lambda db, grouping_key: None,
    )
    monkeypatch.setattr(organisms, "organism_service", fake_service)
    app.dependency_overrides[organisms.get_current_active_user] = override_user
    app.dependency_overrides[organisms.get_db] = override_db

    resp = client.get("/api/v1/organisms")
    assert resp.status_code == 200
    assert resp.json()[0]["grouping_key"] == "g1"

    resp = client.get("/api/v1/organisms/missing")
    assert resp.status_code == 404


def test_create_organism(monkeypatch):
    client = TestClient(app)
    user = SimpleNamespace(is_superuser=False, roles=["curator"], is_active=True)

    def override_user():
        return user

    def override_db():
        yield FakeSession()

    now = datetime.now(timezone.utc)
    fake_service = SimpleNamespace(
        create_organism=lambda db, organism_in: {
            **organism_in.model_dump(),
            "grouping_key": "g1",
            "common_name_source": None,
            "bpa_json": None,
            "taxonomy_lineage_json": None,
            "created_at": now,
            "updated_at": now,
        }
    )
    monkeypatch.setattr(organisms, "organism_service", fake_service)
    monkeypatch.setattr(organisms, "require_role", lambda current_user, roles: None)
    app.dependency_overrides[organisms.get_current_active_user] = override_user
    app.dependency_overrides[organisms.get_db] = override_db

    payload = {
        "grouping_key": "g1",
        "tax_id": 1,
        "scientific_name": "Sci",
        "common_name": "Com",
    }

    resp = client.post("/api/v1/organisms", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["grouping_key"] == "g1"


def test_assemblies_pipeline_inputs_missing_param():
    client = TestClient(app)
    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(is_active=True, roles=["admin"], is_superuser=False)
    app.dependency_overrides[assemblies.get_db] = override_db_map()

    resp = client.get("/api/v1/assemblies/pipeline-inputs")
    assert resp.status_code == 422


def test_assemblies_pipeline_inputs_not_found(monkeypatch):
    client = TestClient(app)
    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(is_active=True, roles=["admin"], is_superuser=False)
    app.dependency_overrides[assemblies.get_db] = override_db_map({})
    monkeypatch.setattr(assemblies.organism_service, "get_by_grouping_key", lambda db, grouping_key: None)

    resp = client.get("/api/v1/assemblies/pipeline-inputs?organism_grouping_key=missing")
    assert resp.status_code == 404


def test_experiment_reads_xml_not_found():
    with pytest.raises(HTTPException) as exc:
        experiment_reads_xml.get_experiment_reads_xml(
            db=FakeSessionMap({}),
            experiment_id=uuid.uuid4(),
            current_user=SimpleNamespace(),
        )
    assert exc.value.status_code == 404


def test_experiment_submission_by_attr_not_found(monkeypatch):
    client = TestClient(app)
    app.dependency_overrides[experiment_submissions.get_current_active_user] = lambda: SimpleNamespace(is_active=True, roles=["admin"], is_superuser=False)
    app.dependency_overrides[experiment_submissions.get_db] = override_db_map({})

    resp = client.get("/api/v1/experiment-submissions/by-experiment-attr?bpa_package_id=missing")
    assert resp.status_code == 404


def test_experiment_submission_by_attr_no_submission():
    client = TestClient(app)
    exp_id = uuid.uuid4()
    app.dependency_overrides[experiment_submissions.get_current_active_user] = lambda: SimpleNamespace(is_active=True, roles=["admin"], is_superuser=False)
    app.dependency_overrides[experiment_submissions.get_db] = override_db_map({
        experiment_submissions.Experiment: [SimpleNamespace(id=exp_id)],
        experiment_submissions.ExperimentSubmission: [],
    })

    resp = client.get(f"/api/v1/experiment-submissions/by-experiment-attr?experiment_id={exp_id}")
    assert resp.status_code == 404


def test_genome_note_not_found():
    client = TestClient(app)
    app.dependency_overrides[genome_notes.get_current_active_user] = lambda: SimpleNamespace(is_active=True, roles=["admin"], is_superuser=False)
    app.dependency_overrides[genome_notes.get_db] = override_db_map({})

    resp = client.get(f"/api/v1/genome-notes/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_read_not_found():
    client = TestClient(app)
    app.dependency_overrides[reads.get_current_active_user] = lambda: SimpleNamespace(is_active=True, roles=["admin"], is_superuser=False)
    app.dependency_overrides[reads.get_db] = override_db_map({})

    resp = client.get(f"/api/v1/reads/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_sample_not_found():
    client = TestClient(app)
    app.dependency_overrides[samples.get_current_active_user] = lambda: SimpleNamespace(is_active=True, roles=["admin"], is_superuser=False)
    app.dependency_overrides[samples.get_db] = override_db_map({})

    resp = client.get(f"/api/v1/samples/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_user_not_found():
    client = TestClient(app)
    app.dependency_overrides[users.get_db] = override_db_map({})

    resp = client.get(f"/api/v1/users/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_xml_export_read_not_found(monkeypatch):
    client = TestClient(app)
    app.dependency_overrides[xml_export.get_current_active_user] = lambda: SimpleNamespace(is_active=True, roles=["admin"], is_superuser=False)
    app.dependency_overrides[xml_export.get_db] = override_db_map({})

    resp = client.get(f"/api/v1/xml-export/reads/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_broker_renew_attempt_not_found():
    fake_db = FakeSessionMap({broker.SubmissionAttempt: []})
    with pytest.raises(HTTPException) as exc:
        broker.renew_attempt_lease(attempt_id=uuid.uuid4(), db=fake_db)  # type: ignore[arg-type]
    assert exc.value.status_code == 404


def test_broker_finalise_attempt_not_found():
    fake_db = FakeSessionMap({broker.SubmissionAttempt: []})
    with pytest.raises(HTTPException) as exc:
        broker.finalise_attempt(attempt_id=uuid.uuid4(), db=fake_db)  # type: ignore[arg-type]
    assert exc.value.status_code == 404

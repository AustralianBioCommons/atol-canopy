from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.v1.endpoints import assemblies
from app.main import app


class _FakeQueryList:
    def __init__(self, data):
        self.data = list(data)

    def filter(self, *_a, **_k):
        return self

    def all(self):
        return list(self.data)


class _FakeSession:
    def query(self, model):
        return _FakeQueryList([])


def _override_db(fake):
    def _gen():
        yield fake

    return _gen


def test_pipeline_inputs_no_samples_returns_empty_files(monkeypatch):
    client = TestClient(app)

    # Mock organism_service to return organism object
    organism = SimpleNamespace(grouping_key="g1", scientific_name="Sci", tax_id=1)
    monkeypatch.setattr(
        assemblies,
        "organism_service",
        SimpleNamespace(get_by_grouping_key=lambda db, key: organism),
    )

    # Active user
    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )
    app.dependency_overrides[assemblies.get_db] = _override_db(_FakeSession())

    resp = client.get("/api/v1/assemblies/pipeline-inputs?organism_grouping_key=g1")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list) and body
    assert body[0]["scientific_name"] == "Sci"
    assert body[0]["files"] == {}


def test_assemblies_pipeline_inputs_missing_param():
    client = TestClient(app)
    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )
    app.dependency_overrides[assemblies.get_db] = _override_db(_FakeSession())

    resp = client.get("/api/v1/assemblies/pipeline-inputs")
    assert resp.status_code == 422


def test_assemblies_pipeline_inputs_not_found(monkeypatch):
    client = TestClient(app)
    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )
    app.dependency_overrides[assemblies.get_db] = _override_db(_FakeSession())
    monkeypatch.setattr(
        assemblies.organism_service, "get_by_grouping_key", lambda db, grouping_key: None
    )

    resp = client.get("/api/v1/assemblies/pipeline-inputs?organism_grouping_key=missing")
    assert resp.status_code == 404


def test_create_assembly_from_experiments_success(monkeypatch):
    """Test successful assembly creation from experiments."""
    from datetime import datetime, timezone
    from uuid import uuid4

    from app.models.assembly import Assembly

    client = TestClient(app)

    # Create a real Assembly object for proper serialization
    mock_assembly = Assembly(
        id=uuid4(),
        organism_key="test_organism",
        sample_id=uuid4(),
        assembly_name="Test Assembly",
        assembly_type="clone or isolate",
        data_types="PACBIO_SMRT",
        coverage=50.0,
        program="hifiasm",
        moleculetype="genomic DNA",
        version=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    platform_info = {
        "platforms": ["PACBIO_SMRT"],
        "library_strategies": ["WGS"],
        "experiment_count": 1,
    }

    monkeypatch.setattr(
        assemblies.assembly_service,
        "create_from_experiments",
        lambda db, tax_id, assembly_in: (mock_assembly, platform_info),
    )

    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["curator"], is_superuser=False
    )
    app.dependency_overrides[assemblies.get_db] = _override_db(_FakeSession())

    resp = client.post(
        "/api/v1/assemblies/from-experiments/172942",
        json={
            "sample_id": "550e8400-e29b-41d4-a716-446655440000",
            "assembly_name": "Test Assembly",
            "assembly_type": "clone or isolate",
            "coverage": 50.0,
            "program": "hifiasm",
            "moleculetype": "genomic DNA",
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    # Response is now just the Assembly schema
    assert "id" in body
    assert body["organism_key"] == "test_organism"
    assert body["data_types"] == "PACBIO_SMRT"
    assert body["assembly_name"] == "Test Assembly"


def test_create_assembly_from_experiments_not_found(monkeypatch):
    """Test error when organism not found."""
    client = TestClient(app)

    def mock_create_raises(*args, **kwargs):
        raise ValueError("Organism with tax_id 999999 not found")

    monkeypatch.setattr(
        assemblies.assembly_service,
        "create_from_experiments",
        mock_create_raises,
    )

    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["curator"], is_superuser=False
    )
    app.dependency_overrides[assemblies.get_db] = _override_db(_FakeSession())

    resp = client.post(
        "/api/v1/assemblies/from-experiments/999999",
        json={
            "sample_id": "550e8400-e29b-41d4-a716-446655440000",
            "assembly_name": "Test Assembly",
            "assembly_type": "clone or isolate",
            "coverage": 50.0,
            "program": "hifiasm",
            "moleculetype": "genomic DNA",
        },
    )

    assert resp.status_code == 400
    response_data = resp.json()
    # Error format may be either {"detail": ...} or {"error": {"message": ...}}
    error_msg = response_data.get("detail") or response_data.get("error", {}).get("message", "")
    assert "not found" in error_msg


def test_get_assembly_manifest_success(monkeypatch):
    """Test successful manifest generation."""
    client = TestClient(app)

    # Mock database queries
    organism = SimpleNamespace(
        grouping_key="test_organism",
        scientific_name="Test Species",
        tax_id=172942,
    )
    sample = SimpleNamespace(id="sample-1", organism_key="test_organism")
    experiment = SimpleNamespace(
        id="exp-1",
        sample_id="sample-1",
        platform="PACBIO_SMRT",
        library_strategy="WGS",
    )
    read = SimpleNamespace(
        id="read-1",
        experiment_id="exp-1",
        file_name="sample.ccs.bam",
        file_checksum="abc123",
        bioplatforms_url="https://example.com/1",
        read_number=None,
        lane_number=None,
    )

    class MockQuery:
        def __init__(self, return_value):
            self.return_value = return_value

        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return self.return_value if not isinstance(self.return_value, list) else None

        def all(self):
            return self.return_value if isinstance(self.return_value, list) else []

    class MockDB:
        def __init__(self):
            self.call_count = 0

        def query(self, model):
            self.call_count += 1
            if self.call_count == 1:  # organism query
                return MockQuery(organism)
            elif self.call_count == 2:  # samples query
                return MockQuery([sample])
            elif self.call_count == 3:  # experiments query
                return MockQuery([experiment])
            elif self.call_count == 4:  # reads query
                return MockQuery([read])
            return MockQuery([])

    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )
    app.dependency_overrides[assemblies.get_db] = lambda: MockDB()

    resp = client.get("/api/v1/assemblies/manifest/172942")

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/x-yaml"
    assert b"scientific_name: Test Species" in resp.content
    assert b"taxon_id: 172942" in resp.content
    assert b"PACBIO_SMRT:" in resp.content


def test_get_assembly_manifest_organism_not_found():
    """Test error when organism not found."""
    client = TestClient(app)

    class MockDB:
        def query(self, model):
            return self

        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return None

    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )
    app.dependency_overrides[assemblies.get_db] = lambda: MockDB()

    resp = client.get("/api/v1/assemblies/manifest/999999")

    assert resp.status_code == 404
    response_data = resp.json()
    # Error format may be either {"detail": ...} or {"error": {"message": ...}}
    error_msg = response_data.get("detail") or response_data.get("error", {}).get("message", "")
    assert "not found" in error_msg

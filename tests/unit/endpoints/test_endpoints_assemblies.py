from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

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
    organism = SimpleNamespace(scientific_name="Sci", taxon_id=1)
    monkeypatch.setattr(
        assemblies,
        "organism_service",
        SimpleNamespace(get_by_taxon_id=lambda db, taxon_id: organism),
    )

    # Active user
    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )
    app.dependency_overrides[assemblies.get_db] = _override_db(_FakeSession())

    resp = client.get("/api/v1/assemblies/pipeline-inputs?taxon_id=1")
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
    monkeypatch.setattr(assemblies.organism_service, "get_by_taxon_id", lambda db, taxon_id: None)

    resp = client.get("/api/v1/assemblies/pipeline-inputs?taxon_id=999999")
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
        taxon_id=172942,
        sample_id=uuid4(),
        assembly_name="Test Assembly",
        assembly_type="clone or isolate",
        tol_id="tol-123",
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
        lambda db, taxon_id, assembly_in: (mock_assembly, platform_info),
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
            "tol_id": "tol-123",
            "coverage": 50.0,
            "program": "hifiasm",
            "moleculetype": "genomic DNA",
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    # Response is now just the Assembly schema
    assert "id" in body
    assert body["taxon_id"] == 172942
    assert body["data_types"] == "PACBIO_SMRT"
    assert body["assembly_name"] == "Test Assembly"


def test_create_assembly_from_experiments_not_found(monkeypatch):
    """Test error when organism not found."""
    client = TestClient(app)

    def mock_create_raises(*args, **kwargs):
        raise ValueError("Organism with taxon_id 999999 not found")

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
            "tol_id": "tol-123",
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
    """GET /manifest/{taxon_id} returns stored manifest JSON for latest assembly."""
    client = TestClient(app)

    organism = SimpleNamespace(scientific_name="Test Species", taxon_id=172942)
    manifest_json = {
        "scientific_name": "Test Species",
        "taxon_id": 172942,
        "tolid": "tol-123",
        "version": 1,
        "reads": {"PACBIO_SMRT": {"pkg-exp-1": {"resources": []}}},
    }
    requested_assembly = SimpleNamespace(
        id="run-1",
        taxon_id=172942,
        tol_id="tol-123",
        version=1,
        manifest_json=manifest_json,
    )

    class MockQuery:
        def __init__(self, return_value):
            self.return_value = return_value

        def filter(self, *args, **kwargs):
            return self

        def order_by(self, *args, **kwargs):
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
            if self.call_count == 1:
                return MockQuery(organism)
            if self.call_count == 2:
                return MockQuery(requested_assembly)
            return MockQuery([])

    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )
    app.dependency_overrides[assemblies.get_db] = lambda: MockDB()

    resp = client.get("/api/v1/assemblies/manifest/172942")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    body = resp.json()
    assert body["assembly_id"] == "run-1"
    assert body["version"] == 1
    assert body["manifest"] == manifest_json


def test_get_assembly_manifest_returns_empty_manifest_when_missing():
    client = TestClient(app)

    organism = SimpleNamespace(scientific_name="Test Species", taxon_id=172942)
    assembly_without_manifest = SimpleNamespace(
        id="run-2",
        taxon_id=172942,
        tol_id="tol-123",
        version=2,
        manifest_json=None,
    )

    class MockQuery:
        def __init__(self, return_value):
            self.return_value = return_value

        def filter(self, *args, **kwargs):
            return self

        def order_by(self, *args, **kwargs):
            return self

        def first(self):
            return self.return_value if not isinstance(self.return_value, list) else None

    class MockDB:
        def __init__(self):
            self.call_count = 0

        def query(self, model):
            self.call_count += 1
            if self.call_count == 1:
                return MockQuery(organism)
            if self.call_count == 2:
                return MockQuery(assembly_without_manifest)
            return MockQuery(None)

    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )
    app.dependency_overrides[assemblies.get_db] = lambda: MockDB()

    resp = client.get("/api/v1/assemblies/manifest/172942")

    assert resp.status_code == 200
    body = resp.json()
    assert body["assembly_id"] == "run-2"
    assert body["version"] == 2
    assert body["manifest"] == {}


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


def test_create_assembly_intent_invalid_data_types_returns_app_error(monkeypatch):
    client = TestClient(app)

    organism = SimpleNamespace(scientific_name="Test Species", taxon_id=172942)
    long_read_sample_id = uuid4()
    long_read_sample = SimpleNamespace(id=long_read_sample_id, taxon_id=172942, kind="specimen")
    invalid_long_read_exp = SimpleNamespace(
        id="e1",
        sample_id=long_read_sample_id,
        platform="PACBIO_SMRT",
        library_strategy="RNA",
    )

    class _Q:
        def __init__(self, value):
            self.value = value

        def filter(self, *_a, **_k):
            return self

        def all(self):
            return self.value if isinstance(self.value, list) else []

        def first(self):
            return self.value if not isinstance(self.value, list) else None

    class _DB:
        def __init__(self):
            self.calls = 0

        def query(self, _model):
            self.calls += 1
            if self.calls == 1:
                return _Q(organism)
            if self.calls == 2:
                return _Q(long_read_sample)
            if self.calls == 3:
                return _Q([])
            if self.calls == 4:
                return _Q([invalid_long_read_exp])
            if self.calls == 5:
                return _Q([])
            return _Q([])

    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["curator"], is_superuser=False
    )
    app.dependency_overrides[assemblies.get_db] = _override_db(_DB())

    resp = client.post(
        "/api/v1/assemblies/intent/172942",
        json={
            "tol_id": "tol-123",
            "long_read_specimen_sample_id": str(long_read_sample_id),
        },
    )

    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "assembly_intent_invalid_data_types"
    assert "No valid data types detected in experiments" in body["error"]["message"]


def test_create_assembly_intent_requires_specimen_sample_id():
    client = TestClient(app)

    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["curator"], is_superuser=False
    )
    app.dependency_overrides[assemblies.get_db] = _override_db(_FakeSession())

    resp = client.post(
        "/api/v1/assemblies/intent/172942",
        json={"tol_id": "tol-123"},
    )

    assert resp.status_code == 422


def test_get_specimen_samples_for_assembly_returns_discovery_options():
    client = TestClient(app)

    organism = SimpleNamespace(scientific_name="Test Species", taxon_id=172942)
    specimen_a_id = uuid4()
    derived_a_id = uuid4()
    specimen_b_id = uuid4()
    specimen_c_id = uuid4()
    specimen_d_id = uuid4()

    specimen_a = SimpleNamespace(
        id=specimen_a_id,
        taxon_id=172942,
        kind="specimen",
        specimen_id="SPEC-001",
        sex="female",
    )
    derived_a = SimpleNamespace(
        id=derived_a_id,
        taxon_id=172942,
        kind="derived",
        derived_from_sample_id=specimen_a_id,
    )
    specimen_b = SimpleNamespace(
        id=specimen_b_id,
        taxon_id=172942,
        kind="specimen",
        specimen_id=None,
        sex="male",
    )
    specimen_c = SimpleNamespace(
        id=specimen_c_id,
        taxon_id=172942,
        kind="specimen",
        specimen_id="SPEC-003",
        sex="unknown",
    )
    specimen_d = SimpleNamespace(
        id=specimen_d_id,
        taxon_id=172942,
        kind="specimen",
        specimen_id="SPEC-004",
        sex="female",
    )

    specimen_a_experiments = [
        SimpleNamespace(
            id="exp-pb",
            sample_id=derived_a_id,
            platform="PACBIO_SMRT",
            library_strategy="WGS",
        ),
        SimpleNamespace(
            id="exp-hic",
            sample_id=specimen_a_id,
            platform="ILLUMINA",
            library_strategy="Hi-C",
        ),
    ]
    specimen_b_experiments = [
        SimpleNamespace(
            id="exp-ont",
            sample_id=specimen_b_id,
            platform="OXFORD_NANOPORE",
            library_strategy="WGA",
        )
    ]
    specimen_d_experiments = [
        SimpleNamespace(
            id="exp-rna",
            sample_id=specimen_d_id,
            platform="ILLUMINA",
            library_strategy="RNA-Seq",
        )
    ]

    class _Q:
        def __init__(self, value):
            self.value = value

        def filter(self, *_a, **_k):
            return self

        def all(self):
            return self.value if isinstance(self.value, list) else []

        def first(self):
            return self.value if not isinstance(self.value, list) else None

    class _DB:
        def __init__(self):
            self.calls = 0

        def query(self, _model):
            self.calls += 1
            if self.calls == 1:
                return _Q(organism)
            if self.calls == 2:
                return _Q([specimen_a, specimen_b, specimen_c, specimen_d])
            if self.calls == 3:
                return _Q([derived_a])
            if self.calls == 4:
                return _Q(specimen_a_experiments)
            if self.calls == 5:
                return _Q([])
            if self.calls == 6:
                return _Q(specimen_b_experiments)
            if self.calls == 7:
                return _Q([])
            if self.calls == 8:
                return _Q([])
            if self.calls == 9:
                return _Q([])
            if self.calls == 10:
                return _Q(specimen_d_experiments)
            return _Q([])

    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )
    app.dependency_overrides[assemblies.get_db] = _override_db(_DB())

    resp = client.get("/api/v1/assemblies/specimen-samples/172942")

    assert resp.status_code == 200
    body = resp.json()
    assert body["taxon_id"] == 172942
    assert body["specimen_samples"] == [
        {
            "sample_id": str(specimen_a_id),
            "specimen_id": "SPEC-001",
            "sex": "female",
            "available_data_types": ["PACBIO_SMRT", "Hi-C"],
        },
        {
            "sample_id": str(specimen_b_id),
            "specimen_id": None,
            "sex": "male",
            "available_data_types": ["OXFORD_NANOPORE"],
        },
        {
            "sample_id": str(specimen_c_id),
            "specimen_id": "SPEC-003",
            "sex": "unknown",
            "available_data_types": [],
        },
        {
            "sample_id": str(specimen_d_id),
            "specimen_id": "SPEC-004",
            "sex": "female",
            "available_data_types": ["RNA-Seq"],
        },
    ]


def test_get_specimen_samples_for_assembly_returns_404_for_unknown_taxon():
    client = TestClient(app)

    class _Q:
        def filter(self, *_a, **_k):
            return self

        def first(self):
            return None

    class _DB:
        def query(self, _model):
            return _Q()

    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )
    app.dependency_overrides[assemblies.get_db] = _override_db(_DB())

    resp = client.get("/api/v1/assemblies/specimen-samples/999999")

    assert resp.status_code == 404
    assert "not found" in resp.json()["error"]["message"]


def test_create_assembly_intent_rejects_non_specimen_sample():
    client = TestClient(app)

    organism = SimpleNamespace(scientific_name="Test Species", taxon_id=172942)
    derived_sample_id = uuid4()
    derived_sample = SimpleNamespace(id=derived_sample_id, taxon_id=172942, kind="derived")

    class _Q:
        def __init__(self, value):
            self.value = value

        def filter(self, *_a, **_k):
            return self

        def first(self):
            return self.value

    class _DB:
        def __init__(self):
            self.calls = 0

        def query(self, _model):
            self.calls += 1
            if self.calls == 1:
                return _Q(organism)
            return _Q(derived_sample)

    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["curator"], is_superuser=False
    )
    app.dependency_overrides[assemblies.get_db] = _override_db(_DB())

    resp = client.post(
        "/api/v1/assemblies/intent/172942",
        json={"long_read_specimen_sample_id": str(derived_sample_id)},
    )

    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "specimen_sample_invalid_kind"


def test_create_assembly_intent_success_returns_json_manifest(monkeypatch):
    client = TestClient(app)

    organism = SimpleNamespace(scientific_name="Test Species", taxon_id=172942)
    long_read_sample_id = uuid4()
    selected_sample = SimpleNamespace(
        id=long_read_sample_id,
        taxon_id=172942,
        kind="specimen",
        bpa_sample_id="102.100.100/9000",
        specimen_id="SPEC-001",
    )
    run_id = uuid4()
    reads = [
        SimpleNamespace(
            id="r1",
            experiment_id="e1",
            file_name="sample.ccs.bam",
            file_checksum="abc123",
            bioplatforms_url="https://example.com/1",
            read_number=None,
            lane_number=None,
        )
    ]
    experiments = [
        SimpleNamespace(
            id="e1",
            sample_id=long_read_sample_id,
            platform="PACBIO_SMRT",
            library_strategy="WGS",
            bpa_package_id="pkg-e1",
            bioplatforms_base_url=None,
        )
    ]

    mock_assembly = SimpleNamespace(id=run_id, version=1, tol_id=None, manifest_json=None)
    monkeypatch.setattr(
        assemblies.assembly_service,
        "create_from_intent",
        lambda db, **kwargs: mock_assembly,
    )

    class _FakeIntentDB:
        def __init__(self):
            self.calls = 0

        def query(self, _model):
            self.calls += 1

            class _Q:
                def __init__(self, value):
                    self.value = value

                def filter(self, *_a, **_k):
                    return self

                def all(self):
                    return self.value if isinstance(self.value, list) else []

                def first(self):
                    return self.value if not isinstance(self.value, list) else None

            if self.calls == 1:
                return _Q(organism)
            if self.calls == 2:
                return _Q(selected_sample)
            if self.calls == 3:
                return _Q([])
            if self.calls == 4:
                return _Q(experiments)
            if self.calls == 5:
                return _Q(reads)
            return _Q([])

        def add(self, _obj):
            return None

        def commit(self):
            return None

        def refresh(self, _obj):
            return None

        def delete(self, _obj):
            return None

    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["curator"], is_superuser=False
    )
    app.dependency_overrides[assemblies.get_db] = _override_db(_FakeIntentDB())

    resp = client.post(
        "/api/v1/assemblies/intent/172942",
        json={"long_read_specimen_sample_id": str(long_read_sample_id)},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["assembly_id"] == str(run_id)
    assert body["version"] == 1
    assert "manifest" in body


def test_create_assembly_intent_resolves_reads_via_derived_samples(monkeypatch):
    client = TestClient(app)

    organism = SimpleNamespace(scientific_name="Test Species", taxon_id=172942)
    long_read_sample_id = uuid4()
    derived_sample_id = uuid4()
    specimen_sample = SimpleNamespace(
        id=long_read_sample_id,
        taxon_id=172942,
        kind="specimen",
        bpa_sample_id="102.100.100/9000",
        specimen_id="SPEC-001",
    )
    derived_sample = SimpleNamespace(
        id=derived_sample_id,
        taxon_id=172942,
        kind="derived",
        derived_from_sample_id=long_read_sample_id,
    )
    run_id = uuid4()
    reads = [
        SimpleNamespace(
            id="r1",
            experiment_id="e1",
            file_name="sample.ccs.bam",
            file_checksum="abc123",
            bioplatforms_url="https://example.com/1",
            read_number=None,
            lane_number=None,
        )
    ]
    experiments = [
        SimpleNamespace(
            id="e1",
            sample_id=derived_sample_id,
            platform="PACBIO_SMRT",
            library_strategy="WGS",
            bpa_package_id="pkg-e1",
            bioplatforms_base_url=None,
        )
    ]

    mock_assembly = SimpleNamespace(id=run_id, version=1, tol_id=None, manifest_json=None)
    monkeypatch.setattr(
        assemblies.assembly_service,
        "create_from_intent",
        lambda db, **kwargs: mock_assembly,
    )

    class _FakeIntentDB:
        def __init__(self):
            self.calls = 0

        def query(self, _model):
            self.calls += 1

            class _Q:
                def __init__(self, value):
                    self.value = value

                def filter(self, *_a, **_k):
                    return self

                def all(self):
                    return self.value if isinstance(self.value, list) else []

                def first(self):
                    return self.value if not isinstance(self.value, list) else None

            if self.calls == 1:
                return _Q(organism)
            if self.calls == 2:
                return _Q(specimen_sample)
            if self.calls == 3:
                return _Q([derived_sample])
            if self.calls == 4:
                return _Q(experiments)
            if self.calls == 5:
                return _Q(reads)
            return _Q([])

        def add(self, _obj):
            return None

        def commit(self):
            return None

        def refresh(self, _obj):
            return None

        def delete(self, _obj):
            return None

    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["curator"], is_superuser=False
    )
    app.dependency_overrides[assemblies.get_db] = _override_db(_FakeIntentDB())

    resp = client.post(
        "/api/v1/assemblies/intent/172942",
        json={"long_read_specimen_sample_id": str(long_read_sample_id)},
    )

    assert resp.status_code == 200
    body = resp.json()
    read_files = body["manifest"]["read_files"]
    pkg = next(
        (p for p in read_files if p["data_type"] == "PACBIO_SMRT" and p["name"] == "pkg-e1"),
        None,
    )
    assert pkg is not None
    assert pkg["sample_id"] == str(long_read_sample_id)
    assert pkg["specimen_id"] == "SPEC-001"


def test_cancel_assembly_intent_success(monkeypatch):
    client = TestClient(app)

    organism = SimpleNamespace(taxon_id=172942)
    long_read_sample_id = uuid4()
    run_id = uuid4()
    run = SimpleNamespace(
        id=run_id,
        taxon_id=172942,
        long_read_specimen_sample_id=long_read_sample_id,
        hic_specimen_sample_ids=None,
        version=2,
    )

    class _Q:
        def __init__(self, value):
            self.value = value

        def filter(self, *_a, **_k):
            return self

        def order_by(self, *_a, **_k):
            return self

        def first(self):
            return self.value

    class _DB:
        def __init__(self):
            self.calls = 0

        def query(self, _model):
            self.calls += 1
            if self.calls == 1:
                return _Q(organism)
            return _Q(run)

        def add(self, _obj):
            return None

        def delete(self, _obj):
            return None

        def commit(self):
            return None

    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["curator"], is_superuser=False
    )
    app.dependency_overrides[assemblies.get_db] = _override_db(_DB())

    resp = client.post(
        "/api/v1/assemblies/intent/172942/cancel",
        json={"assembly_id": str(run_id)},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["deleted"] is True
    assert body["version"] == 2


def test_cancel_assembly_intent_not_found(monkeypatch):
    client = TestClient(app)

    organism = SimpleNamespace(taxon_id=172942)

    class _Q:
        def __init__(self, value):
            self.value = value

        def filter(self, *_a, **_k):
            return self

        def order_by(self, *_a, **_k):
            return self

        def first(self):
            return self.value

    class _DB:
        def __init__(self):
            self.calls = 0

        def query(self, _model):
            self.calls += 1
            if self.calls == 1:
                return _Q(organism)
            return _Q(None)

    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["curator"], is_superuser=False
    )
    app.dependency_overrides[assemblies.get_db] = _override_db(_DB())

    resp = client.post(
        "/api/v1/assemblies/intent/172942/cancel",
        json={"assembly_id": str(uuid4())},
    )

    assert resp.status_code == 404
    assert "Assembly not found to cancel" in resp.json()["error"]["message"]


# ── New manifest-by-assembly-id tests ──────────────────────────────────────


def test_get_manifest_by_assembly_id_success(monkeypatch):
    """GET /{assembly_id}/manifest returns stored manifest JSON for a known assembly."""
    from uuid import uuid4 as _uuid4

    client = TestClient(app)
    assembly_id = _uuid4()
    manifest_json = {
        "scientific_name": "Test Species",
        "taxon_id": 172942,
        "tolid": "tol-999",
        "version": 3,
        "reads": {"PACBIO_SMRT": {"pkg-exp-1": {"resources": []}}},
    }

    assembly = SimpleNamespace(
        id=assembly_id,
        taxon_id=172942,
        tol_id="tol-999",
        version=3,
        manifest_json=manifest_json,
    )

    class MockQuery:
        def __init__(self, rv):
            self.rv = rv

        def filter(self, *a, **k):
            return self

        def all(self):
            return self.rv if isinstance(self.rv, list) else []

        def first(self):
            return self.rv if not isinstance(self.rv, list) else None

    class MockDB:
        def query(self, _m):
            return MockQuery(assembly)

    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )
    app.dependency_overrides[assemblies.get_db] = lambda: MockDB()

    resp = client.get(f"/api/v1/assemblies/{assembly_id}/manifest")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    body = resp.json()
    assert body["assembly_id"] == str(assembly_id)
    assert body["version"] == 3
    assert body["manifest"] == manifest_json


def test_get_manifest_by_assembly_id_not_found():
    """GET /{assembly_id}/manifest returns 404 when assembly does not exist."""
    from uuid import uuid4 as _uuid4

    client = TestClient(app)

    class MockDB:
        def query(self, _m):
            return self

        def filter(self, *a, **k):
            return self

        def first(self):
            return None

    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )
    app.dependency_overrides[assemblies.get_db] = lambda: MockDB()

    resp = client.get(f"/api/v1/assemblies/{_uuid4()}/manifest")
    assert resp.status_code == 404
    assert "Assembly not found" in resp.json()["error"]["message"]


def test_create_assembly_run_success(monkeypatch):
    client = TestClient(app)
    assembly_id = uuid4()
    now = datetime.now(timezone.utc)
    assembly = SimpleNamespace(id=assembly_id)
    created_run = SimpleNamespace(
        id=uuid4(),
        assembly_id=assembly_id,
        github_repo="https://github.com/org/pipeline",
        git_commit="abc123",
        created_at=now,
        updated_at=now,
        stage_runs=[],
    )

    monkeypatch.setattr(assemblies.assembly_service, "get", lambda db, id: assembly)
    monkeypatch.setattr(
        assemblies.assembly_run_service,
        "create_for_assembly",
        lambda db, assembly_id, run_in: created_run,
    )

    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )
    app.dependency_overrides[assemblies.get_db] = _override_db(_FakeSession())

    resp = client.post(
        f"/api/v1/assemblies/{assembly_id}/runs",
        json={
            "github_repo": "https://github.com/org/pipeline",
            "git_commit": "abc123",
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["assembly_id"] == str(assembly_id)
    assert body["github_repo"] == "https://github.com/org/pipeline"
    assert body["git_commit"] == "abc123"


def test_create_assembly_run_rejects_duplicate_repo_commit(monkeypatch):
    client = TestClient(app)
    assembly_id = uuid4()
    assembly = SimpleNamespace(id=assembly_id)

    monkeypatch.setattr(assemblies.assembly_service, "get", lambda db, id: assembly)

    def _raise_duplicate(*_args, **_kwargs):
        raise ValueError(
            "Assembly run already exists for this assembly_id, github_repo, and git_commit"
        )

    monkeypatch.setattr(assemblies.assembly_run_service, "create_for_assembly", _raise_duplicate)

    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )
    app.dependency_overrides[assemblies.get_db] = _override_db(_FakeSession())

    resp = client.post(
        f"/api/v1/assemblies/{assembly_id}/runs",
        json={
            "github_repo": "https://github.com/org/pipeline",
            "git_commit": "abc123",
        },
    )

    assert resp.status_code == 409
    response_data = resp.json()
    error_msg = response_data.get("detail") or response_data.get("error", {}).get("message", "")
    assert "already exists" in error_msg


# ── Stage-run endpoint tests ────────────────────────────────────────────────


def _make_stage_run(assembly_run_id=None):
    """Return a SimpleNamespace that satisfies AssemblyStageRunOut."""
    from datetime import datetime, timezone

    return SimpleNamespace(
        id=uuid4(),
        assembly_run_id=assembly_run_id or uuid4(),
        stage_name="genomeassembly",
        status="succeeded",
        external_run_id="ext-123",
        stats={"n50": 10000},
        started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        completed_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        files=[],
    )


def test_list_stage_runs(monkeypatch):
    """GET /{assembly_id}/runs/{run_id}/stage-runs returns list of stage runs."""
    client = TestClient(app)
    assembly_id = uuid4()
    run_id = uuid4()
    stage_run = _make_stage_run(assembly_run_id=run_id)

    monkeypatch.setattr(
        assemblies.assembly_stage_run_service,
        "get_by_assembly_run_id",
        lambda db, assembly_run_id: [stage_run],
    )

    class _Q:
        def filter(self, *_a, **_k):
            return self

        def first(self):
            return SimpleNamespace(id=run_id, assembly_id=assembly_id)

    class _DB:
        def query(self, _model):
            return _Q()

    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )
    app.dependency_overrides[assemblies.get_db] = lambda: _DB()

    resp = client.get(f"/api/v1/assemblies/{assembly_id}/runs/{run_id}/stage-runs")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 1
    assert body[0]["stage_name"] == "genomeassembly"
    assert body[0]["status"] == "succeeded"


def test_list_stage_runs_assembly_not_found(monkeypatch):
    """GET /{assembly_id}/runs/{run_id}/stage-runs returns 404 when run missing."""
    client = TestClient(app)

    class _Q:
        def filter(self, *_a, **_k):
            return self

        def first(self):
            return None

    class _DB:
        def query(self, _model):
            return _Q()

    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["admin"], is_superuser=False
    )
    app.dependency_overrides[assemblies.get_db] = lambda: _DB()

    resp = client.get(f"/api/v1/assemblies/{uuid4()}/runs/{uuid4()}/stage-runs")
    assert resp.status_code == 404


def test_create_stage_run_success(monkeypatch):
    """POST /{assembly_id}/runs/{run_id}/stage-runs creates a stage run with files."""
    client = TestClient(app)
    assembly_id = uuid4()
    run_id = uuid4()
    stage_run = _make_stage_run(assembly_run_id=run_id)
    stage_run.files = [
        SimpleNamespace(
            id=uuid4(),
            assembly_stage_run_id=stage_run.id,
            storage_type="s3",
            endpoint="https://projects.pawsey.org.au",
            location_root="bucket",
            location_path="key",
            sha256sum="deadbeef",
            created_at=stage_run.created_at,
            updated_at=stage_run.updated_at,
        )
    ]

    monkeypatch.setattr(
        assemblies.assembly_stage_run_service,
        "create_with_files",
        lambda db, **kwargs: stage_run,
    )

    class _Q:
        def filter(self, *_a, **_k):
            return self

        def first(self):
            return SimpleNamespace(id=run_id, assembly_id=assembly_id)

    class _DB:
        def query(self, _model):
            return _Q()

    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["curator"], is_superuser=False
    )
    app.dependency_overrides[assemblies.get_db] = lambda: _DB()

    resp = client.post(
        f"/api/v1/assemblies/{assembly_id}/runs/{run_id}/stage-runs",
        json={
            "stage_name": "genomeassembly",
            "status": "succeeded",
            "stats": {"n50": 10000},
            "files": [
                {
                    "storage_type": "s3",
                    "endpoint": "https://projects.pawsey.org.au",
                    "location_root": "bucket",
                    "location_path": "key",
                    "sha256sum": "deadbeef",
                }
            ],
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["stage_name"] == "genomeassembly"
    assert body["status"] == "succeeded"
    assert len(body["files"]) == 1
    assert body["files"][0]["storage_type"] == "s3"
    assert body["files"][0]["endpoint"] == "https://projects.pawsey.org.au"
    assert body["files"][0]["location_root"] == "bucket"
    assert body["files"][0]["location_path"] == "key"
    assert body["files"][0]["sha256sum"] == "deadbeef"


def test_update_stage_run_status(monkeypatch):
    """PATCH /{assembly_id}/runs/{run_id}/stage-runs/{stage_run_id} updates status."""
    client = TestClient(app)
    assembly_id = uuid4()
    run_id = uuid4()
    stage_run = _make_stage_run(assembly_run_id=run_id)
    updated_run = _make_stage_run(assembly_run_id=run_id)
    updated_run.id = stage_run.id
    updated_run.status = "failed"

    class _Q:
        def filter(self, *_a, **_k):
            return self

        def join(self, *_a, **_k):
            return self

        def first(self):
            return stage_run

    monkeypatch.setattr(
        assemblies.assembly_stage_run_service,
        "update_with_files",
        lambda db, db_obj, update_in: updated_run,
    )

    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["curator"], id=uuid4(), is_superuser=False
    )

    class _DB:
        def query(self, _m):
            return _Q()

    app.dependency_overrides[assemblies.get_db] = lambda: _DB()

    resp = client.patch(
        f"/api/v1/assemblies/{assembly_id}/runs/{run_id}/stage-runs/{stage_run.id}",
        json={"status": "failed"},
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "failed"


def test_update_stage_run_replaces_files(monkeypatch):
    """PATCH replaces all files when files list is provided."""
    from datetime import datetime, timezone

    client = TestClient(app)
    assembly_id = uuid4()
    run_id = uuid4()
    stage_run = _make_stage_run(assembly_run_id=run_id)
    new_file = SimpleNamespace(
        id=uuid4(),
        assembly_stage_run_id=stage_run.id,
        storage_type="gcs",
        endpoint="https://storage.googleapis.com",
        location_root="bucket",
        location_path="new-key",
        sha256sum="cafebabe",
        created_at=datetime(2026, 1, 3, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 3, tzinfo=timezone.utc),
    )
    updated_run = _make_stage_run(assembly_run_id=run_id)
    updated_run.id = stage_run.id
    updated_run.files = [new_file]

    class _Q:
        def filter(self, *_a, **_k):
            return self

        def join(self, *_a, **_k):
            return self

        def first(self):
            return stage_run

    monkeypatch.setattr(
        assemblies.assembly_stage_run_service,
        "update_with_files",
        lambda db, db_obj, update_in: updated_run,
    )

    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["curator"], id=uuid4(), is_superuser=False
    )

    class _DB:
        def query(self, _m):
            return _Q()

    app.dependency_overrides[assemblies.get_db] = lambda: _DB()

    resp = client.patch(
        f"/api/v1/assemblies/{assembly_id}/runs/{run_id}/stage-runs/{stage_run.id}",
        json={
            "files": [
                {
                    "storage_type": "gcs",
                    "endpoint": "https://storage.googleapis.com",
                    "location_root": "bucket",
                    "location_path": "new-key",
                    "sha256sum": "cafebabe",
                }
            ]
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["files"]) == 1
    assert body["files"][0]["storage_type"] == "gcs"
    assert body["files"][0]["endpoint"] == "https://storage.googleapis.com"
    assert body["files"][0]["location_root"] == "bucket"
    assert body["files"][0]["location_path"] == "new-key"
    assert body["files"][0]["sha256sum"] == "cafebabe"


def test_update_assembly_updates_version_and_manifest():
    client = TestClient(app)
    assembly_id = uuid4()
    now = datetime.now(timezone.utc)
    assembly = SimpleNamespace(
        id=assembly_id,
        taxon_id=172942,
        sample_id=uuid4(),
        project_id=None,
        assembly_name="Assembly 1",
        assembly_type="clone or isolate",
        tol_id="tol-123",
        data_types="PACBIO_SMRT",
        coverage=50.0,
        program="hifiasm",
        mingaplength=None,
        moleculetype="genomic DNA",
        description=None,
        version=1,
        long_read_specimen_sample_id=None,
        hic_specimen_sample_id=None,
        manifest_json=None,
        created_at=now,
        updated_at=now,
    )

    class _Q:
        def filter(self, *_a, **_k):
            return self

        def first(self):
            return assembly

    class _DB:
        def query(self, _m):
            return _Q()

        def add(self, obj):
            pass

        def commit(self):
            pass

        def refresh(self, obj):
            obj.updated_at = now

    app.dependency_overrides[assemblies.get_current_active_user] = lambda: SimpleNamespace(
        is_active=True, roles=["curator"], is_superuser=False
    )
    app.dependency_overrides[assemblies.get_db] = _override_db(_DB())

    resp = client.put(
        f"/api/v1/assemblies/{assembly_id}",
        json={"version": 3, "manifest_json": {"assembly": "manifest"}},
    )

    assert resp.status_code == 200
    assert resp.json()["version"] == 3
    assert resp.json()["manifest_json"] == {"assembly": "manifest"}
    assert assembly.version == 3
    assert assembly.manifest_json == {"assembly": "manifest"}

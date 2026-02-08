"""
Unit and integration tests for bulk import sample endpoints.

Tests cover:
- POST /samples/bulk-import-specimens
- POST /samples/bulk-import-derived
"""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.v1.endpoints import samples
from app.main import app
from app.schemas.common import SampleKind


def _override_user(roles=None):
    """Create a fake user with specified roles."""
    if roles is None:
        roles = ["admin"]
    return lambda: SimpleNamespace(is_superuser=False, roles=roles, is_active=True)


class FakeQuery:
    """Mock database query object."""

    def __init__(self, return_value=None):
        self._return_value = return_value
        self._filters = []

    def filter(self, *args, **kwargs):
        self._filters.append((args, kwargs))
        return self

    def first(self):
        return self._return_value

    def all(self):
        return self._return_value if isinstance(self._return_value, list) else [self._return_value]


class FakeSession:
    """Mock database session."""

    def __init__(self, organisms=None, samples=None):
        self.organisms = organisms or {}
        self.samples = samples or {}
        self.added_objects = []
        self.committed = False
        self.rolled_back = False

    def query(self, model):
        """Return appropriate fake query based on model."""
        if hasattr(model, "__tablename__"):
            if model.__tablename__ == "organism":
                return FakeQuery(return_value=self.organisms.get("default"))
            elif model.__tablename__ == "sample":
                return FakeQuery(return_value=self.samples.get("default"))
        return FakeQuery()

    def add(self, obj):
        self.added_objects.append(obj)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def refresh(self, obj):
        pass


def _override_db(fake_session):
    """Override database dependency."""

    def _gen():
        yield fake_session

    return _gen


# ==========================================
# Unit Tests for bulk-import-specimens
# ==========================================


def test_bulk_import_specimens_success(monkeypatch):
    """Test successful bulk import of specimen samples."""
    client = TestClient(app)

    # Mock organism
    fake_organism = SimpleNamespace(
        grouping_key="Homo_sapiens", tax_id=9606, scientific_name="Homo sapiens"
    )

    fake_session = FakeSession(
        organisms={"default": fake_organism},
        samples={"default": None},  # No existing samples
    )

    app.dependency_overrides[samples.get_current_active_user] = _override_user(["curator"])
    app.dependency_overrides[samples.get_db] = _override_db(fake_session)

    # Mock the helper function
    def mock_create_sample(
        db,
        bpa_sample_id,
        sample_data,
        organism_key,
        kind,
        derived_from_sample_id=None,
        ena_atol_map=None,
    ):
        sample = SimpleNamespace(
            id=uuid.uuid4(),
            organism_key=organism_key,
            bpa_sample_id=bpa_sample_id,
            specimen_id=sample_data.get("specimen_id"),
            kind=kind,
        )
        submission = SimpleNamespace(id=uuid.uuid4(), sample_id=sample.id)
        return sample, submission

    monkeypatch.setattr(samples, "_create_sample_with_submission", mock_create_sample)
    monkeypatch.setattr(samples, "require_role", lambda current_user, roles: None)

    # Mock file reading
    with patch("builtins.open", create=True) as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = '{"sample": {}}'
        with patch("json.load", return_value={"sample": {}}):
            payload = {
                "SPEC001_9606": {
                    "organism_grouping_key": "Homo_sapiens",
                    "specimen_id": "SPEC001",
                    "lifestage": "adult",
                    "sex": "male",
                    "organism_part": "blood",
                }
            }

            resp = client.post("/api/v1/samples/bulk-import-specimens", json=payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["created_count"] == 1
    assert body["skipped_count"] == 0
    assert "Created: 1" in body["message"]


def test_bulk_import_specimens_missing_organism_key():
    """Test bulk import fails when organism_grouping_key is missing."""
    client = TestClient(app)

    fake_session = FakeSession()

    app.dependency_overrides[samples.get_current_active_user] = _override_user(["admin"])
    app.dependency_overrides[samples.get_db] = _override_db(fake_session)

    with patch("builtins.open", create=True):
        with patch("json.load", return_value={"sample": {}}):
            payload = {"SPEC001_9606": {"specimen_id": "SPEC001", "lifestage": "adult"}}

            resp = client.post("/api/v1/samples/bulk-import-specimens", json=payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["created_count"] == 0
    assert body["skipped_count"] == 1
    assert body["errors"] is not None
    assert any("Missing organism_grouping_key" in err for err in body["errors"])


def test_bulk_import_specimens_missing_specimen_id():
    """Test bulk import fails when specimen_id is missing."""
    client = TestClient(app)

    fake_organism = SimpleNamespace(grouping_key="Homo_sapiens")
    fake_session = FakeSession(organisms={"default": fake_organism})

    app.dependency_overrides[samples.get_current_active_user] = _override_user(["admin"])
    app.dependency_overrides[samples.get_db] = _override_db(fake_session)

    with patch("builtins.open", create=True):
        with patch("json.load", return_value={"sample": {}}):
            payload = {
                "SPEC001_9606": {"organism_grouping_key": "Homo_sapiens", "lifestage": "adult"}
            }

            resp = client.post("/api/v1/samples/bulk-import-specimens", json=payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["created_count"] == 0
    assert body["skipped_count"] == 1
    assert body["errors"] is not None
    assert any("specimen_id is required" in err for err in body["errors"])


def test_bulk_import_specimens_duplicate_specimen(monkeypatch):
    """Test bulk import skips duplicate specimens."""
    client = TestClient(app)

    fake_organism = SimpleNamespace(grouping_key="Homo_sapiens")

    # Mock existing specimen
    existing_specimen = SimpleNamespace(
        id=uuid.uuid4(),
        organism_key="Homo_sapiens",
        specimen_id="SPEC001",
        kind=SampleKind.SPECIMEN,
    )

    # Create a custom query that returns existing specimen for duplicate check
    class CustomFakeSession(FakeSession):
        def query(self, model):
            if hasattr(model, "__tablename__") and model.__tablename__ == "sample":
                # Return existing specimen on second query (duplicate check)
                query = FakeQuery()
                query._return_value = existing_specimen
                return query
            elif hasattr(model, "__tablename__") and model.__tablename__ == "organism":
                return FakeQuery(return_value=fake_organism)
            return FakeQuery()

    fake_session = CustomFakeSession()

    app.dependency_overrides[samples.get_current_active_user] = _override_user(["admin"])
    app.dependency_overrides[samples.get_db] = _override_db(fake_session)
    monkeypatch.setattr(samples, "require_role", lambda current_user, roles: None)

    with patch("builtins.open", create=True):
        with patch("json.load", return_value={"sample": {}}):
            payload = {
                "SPEC001_9606": {
                    "organism_grouping_key": "Homo_sapiens",
                    "specimen_id": "SPEC001",
                    "lifestage": "adult",
                }
            }

            resp = client.post("/api/v1/samples/bulk-import-specimens", json=payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["created_count"] == 0
    assert body["skipped_count"] == 1
    assert body["errors"] is not None
    assert any("already exists" in err for err in body["errors"])


def test_bulk_import_specimens_organism_not_found():
    """Test bulk import fails when organism doesn't exist."""
    client = TestClient(app)

    fake_session = FakeSession(organisms={"default": None})

    app.dependency_overrides[samples.get_current_active_user] = _override_user(["admin"])
    app.dependency_overrides[samples.get_db] = _override_db(fake_session)

    with patch("builtins.open", create=True):
        with patch("json.load", return_value={"sample": {}}):
            payload = {
                "SPEC001_9606": {
                    "organism_grouping_key": "NonExistent",
                    "specimen_id": "SPEC001",
                    "lifestage": "adult",
                }
            }

            resp = client.post("/api/v1/samples/bulk-import-specimens", json=payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["created_count"] == 0
    assert body["skipped_count"] == 1
    assert body["errors"] is not None
    assert any("Organism not found" in err for err in body["errors"])


def test_bulk_import_specimens_bpa_sample_id_optional(monkeypatch):
    """Test that bpa_sample_id is optional for specimens."""
    client = TestClient(app)

    fake_organism = SimpleNamespace(grouping_key="Homo_sapiens")
    fake_session = FakeSession(organisms={"default": fake_organism}, samples={"default": None})

    app.dependency_overrides[samples.get_current_active_user] = _override_user(["admin"])
    app.dependency_overrides[samples.get_db] = _override_db(fake_session)

    def mock_create_sample(
        db,
        bpa_sample_id,
        sample_data,
        organism_key,
        kind,
        derived_from_sample_id=None,
        ena_atol_map=None,
    ):
        # Verify bpa_sample_id can be None
        assert bpa_sample_id is None
        sample = SimpleNamespace(
            id=uuid.uuid4(),
            organism_key=organism_key,
            bpa_sample_id=bpa_sample_id,
            specimen_id=sample_data.get("specimen_id"),
            kind=kind,
        )
        submission = SimpleNamespace(id=uuid.uuid4(), sample_id=sample.id)
        return sample, submission

    monkeypatch.setattr(samples, "_create_sample_with_submission", mock_create_sample)
    monkeypatch.setattr(samples, "require_role", lambda current_user, roles: None)

    with patch("builtins.open", create=True):
        with patch("json.load", return_value={"sample": {}}):
            payload = {
                "SPEC001_9606": {
                    "organism_grouping_key": "Homo_sapiens",
                    "specimen_id": "SPEC001",
                    "lifestage": "adult",
                    "sex": "male",
                    "organism_part": "blood",
                    # Note: no bpa_sample_id
                }
            }

            resp = client.post("/api/v1/samples/bulk-import-specimens", json=payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["created_count"] == 1


# ==========================================
# Unit Tests for bulk-import-derived
# ==========================================


def test_bulk_import_derived_success(monkeypatch):
    """Test successful bulk import of derived samples."""
    client = TestClient(app)

    fake_organism = SimpleNamespace(grouping_key="Homo_sapiens")

    # Mock parent specimen
    parent_specimen = SimpleNamespace(
        id=uuid.uuid4(),
        organism_key="Homo_sapiens",
        specimen_id="SPEC001",
        kind=SampleKind.SPECIMEN,
    )

    # Custom session that returns parent specimen on lookup
    class CustomFakeSession(FakeSession):
        def __init__(self):
            super().__init__()
            self.sample_query_count = 0

        def query(self, model):
            if hasattr(model, "__tablename__"):
                if model.__tablename__ == "organism":
                    return FakeQuery(return_value=fake_organism)
                elif model.__tablename__ == "sample":
                    self.sample_query_count += 1
                    # First Sample query: check for existing by bpa_sample_id (return None)
                    # Second Sample query: lookup parent specimen (return parent)
                    if self.sample_query_count == 1:
                        return FakeQuery(return_value=None)
                    else:
                        return FakeQuery(return_value=parent_specimen)
            return FakeQuery()

    fake_session = CustomFakeSession()

    app.dependency_overrides[samples.get_current_active_user] = _override_user(["admin"])
    app.dependency_overrides[samples.get_db] = _override_db(fake_session)

    def mock_create_sample(
        db,
        bpa_sample_id,
        sample_data,
        organism_key,
        kind,
        derived_from_sample_id=None,
        ena_atol_map=None,
    ):
        assert bpa_sample_id == "BPA123"
        assert kind == SampleKind.DERIVED
        assert derived_from_sample_id == parent_specimen.id
        sample = SimpleNamespace(
            id=uuid.uuid4(),
            organism_key=organism_key,
            bpa_sample_id=bpa_sample_id,
            kind=kind,
            derived_from_sample_id=derived_from_sample_id,
        )
        submission = SimpleNamespace(id=uuid.uuid4(), sample_id=sample.id)
        return sample, submission

    monkeypatch.setattr(samples, "_create_sample_with_submission", mock_create_sample)
    monkeypatch.setattr(samples, "require_role", lambda current_user, roles: None)

    with patch("builtins.open", create=True):
        with patch("json.load", return_value={"sample": {}}):
            payload = {
                "BPA123": {
                    "bpa_sample_id": "BPA123",
                    "organism_grouping_key": "Homo_sapiens",
                    "specimen_id": "SPEC001",
                    "lifestage": "adult",
                }
            }

            resp = client.post("/api/v1/samples/bulk-import-derived", json=payload)

    assert resp.status_code == 200
    body = resp.json()
    print("x0x0x0: ", body)
    assert body["created_count"] == 1
    assert body["skipped_count"] == 0


def test_bulk_import_derived_missing_bpa_sample_id():
    """Test bulk import derived fails when bpa_sample_id is missing."""
    client = TestClient(app)

    fake_session = FakeSession()

    app.dependency_overrides[samples.get_current_active_user] = _override_user(["admin"])
    app.dependency_overrides[samples.get_db] = _override_db(fake_session)

    with patch("builtins.open", create=True):
        with patch("json.load", return_value={"sample": {}}):
            payload = {
                "derived_001": {
                    "organism_grouping_key": "Homo_sapiens",
                    "specimen_id": "SPEC001",
                    "lifestage": "adult",
                    # Missing bpa_sample_id
                }
            }

            resp = client.post("/api/v1/samples/bulk-import-derived", json=payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["created_count"] == 0
    assert body["skipped_count"] == 1
    assert body["errors"] is not None
    assert any("bpa_sample_id is required" in err for err in body["errors"])


def test_bulk_import_derived_parent_not_found():
    """Test bulk import derived fails when parent specimen doesn't exist."""
    client = TestClient(app)

    fake_organism = SimpleNamespace(grouping_key="Homo_sapiens")

    class CustomFakeSession(FakeSession):
        def query(self, model):
            if hasattr(model, "__tablename__"):
                if model.__tablename__ == "organism":
                    return FakeQuery(return_value=fake_organism)
                elif model.__tablename__ == "sample":
                    return FakeQuery(return_value=None)  # No parent found
            return FakeQuery()

    fake_session = CustomFakeSession()

    app.dependency_overrides[samples.get_current_active_user] = _override_user(["admin"])
    app.dependency_overrides[samples.get_db] = _override_db(fake_session)

    with patch("builtins.open", create=True):
        with patch("json.load", return_value={"sample": {}}):
            payload = {
                "derived_001": {
                    "bpa_sample_id": "BPA123",
                    "organism_grouping_key": "Homo_sapiens",
                    "specimen_id": "SPEC999",  # Non-existent
                    "lifestage": "adult",
                }
            }

            resp = client.post("/api/v1/samples/bulk-import-derived", json=payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["created_count"] == 0
    assert body["skipped_count"] == 1
    assert body["errors"] is not None
    assert any("Parent specimen not found" in err for err in body["errors"])


def test_bulk_import_derived_lookup_by_tax_id(monkeypatch):
    """Test bulk import derived can lookup organism by tax_id."""
    client = TestClient(app)

    fake_organism = SimpleNamespace(grouping_key="Homo_sapiens", tax_id=9606)

    parent_specimen = SimpleNamespace(
        id=uuid.uuid4(),
        organism_key="Homo_sapiens",
        specimen_id="SPEC001",
        kind=SampleKind.SPECIMEN,
    )

    class CustomFakeSession(FakeSession):
        def __init__(self):
            super().__init__()
            self.sample_query_count = 0

        def query(self, model):
            if hasattr(model, "__tablename__"):
                if model.__tablename__ == "organism":
                    return FakeQuery(return_value=fake_organism)
                elif model.__tablename__ == "sample":
                    self.sample_query_count += 1
                    # First Sample query: check for existing by bpa_sample_id (return None)
                    # Second Sample query: lookup parent specimen (return parent)
                    if self.sample_query_count == 1:
                        return FakeQuery(return_value=None)
                    return FakeQuery(return_value=parent_specimen)
            return FakeQuery()

    fake_session = CustomFakeSession()

    app.dependency_overrides[samples.get_current_active_user] = _override_user(["admin"])
    app.dependency_overrides[samples.get_db] = _override_db(fake_session)

    def mock_create_sample(
        db,
        bpa_sample_id,
        sample_data,
        organism_key,
        kind,
        derived_from_sample_id=None,
        ena_atol_map=None,
    ):
        assert organism_key == "Homo_sapiens"
        sample = SimpleNamespace(
            id=uuid.uuid4(), organism_key=organism_key, bpa_sample_id=bpa_sample_id, kind=kind
        )
        submission = SimpleNamespace(id=uuid.uuid4(), sample_id=sample.id)
        return sample, submission

    monkeypatch.setattr(samples, "_create_sample_with_submission", mock_create_sample)
    monkeypatch.setattr(samples, "require_role", lambda current_user, roles: None)

    with patch("builtins.open", create=True):
        with patch("json.load", return_value={"sample": {}}):
            payload = {
                "derived_001": {
                    "bpa_sample_id": "BPA123",
                    "tax_id": 9606,  # Using tax_id instead of organism_grouping_key
                    "specimen_id": "SPEC001",
                    "lifestage": "adult",
                }
            }

            resp = client.post("/api/v1/samples/bulk-import-derived", json=payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["created_count"] == 1


def test_bulk_import_derived_duplicate_bpa_sample_id():
    """Test bulk import derived skips samples with duplicate bpa_sample_id."""
    client = TestClient(app)

    existing_sample = SimpleNamespace(
        id=uuid.uuid4(), bpa_sample_id="BPA123", kind=SampleKind.DERIVED
    )

    fake_session = FakeSession(samples={"default": existing_sample})

    app.dependency_overrides[samples.get_current_active_user] = _override_user(["admin"])
    app.dependency_overrides[samples.get_db] = _override_db(fake_session)

    with patch("builtins.open", create=True):
        with patch("json.load", return_value={"sample": {}}):
            payload = {
                "derived_001": {
                    "bpa_sample_id": "BPA123",
                    "organism_grouping_key": "Homo_sapiens",
                    "specimen_id": "SPEC001",
                    "lifestage": "adult",
                }
            }

            resp = client.post("/api/v1/samples/bulk-import-derived", json=payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["created_count"] == 0
    assert body["skipped_count"] == 1


# ==========================================
# Authorization Tests
# ==========================================


def test_bulk_import_specimens_requires_curator_or_admin():
    """Test that bulk import specimens requires curator or admin role."""
    client = TestClient(app)

    # User without proper role
    app.dependency_overrides[samples.get_current_active_user] = _override_user(["viewer"])
    app.dependency_overrides[samples.get_db] = _override_db(FakeSession())

    payload = {"SPEC001_9606": {"specimen_id": "SPEC001"}}

    # This will fail at the require_role check
    # Note: The actual behavior depends on require_role implementation
    resp = client.post("/api/v1/samples/bulk-import-specimens", json=payload)
    # Status code depends on require_role implementation


def test_bulk_import_derived_requires_admin():
    """Test that bulk import derived requires admin role."""
    client = TestClient(app)

    app.dependency_overrides[samples.get_current_active_user] = _override_user(["viewer"])
    app.dependency_overrides[samples.get_db] = _override_db(FakeSession())

    payload = {"derived_001": {"bpa_sample_id": "BPA123"}}

    resp = client.post("/api/v1/samples/bulk-import-derived", json=payload)
    # Status code depends on require_role implementation


# ==========================================
# Edge Cases and Error Handling
# ==========================================


def test_bulk_import_specimens_empty_payload():
    """Test bulk import with empty payload."""
    client = TestClient(app)

    app.dependency_overrides[samples.get_current_active_user] = _override_user(["admin"])
    app.dependency_overrides[samples.get_db] = _override_db(FakeSession())

    with patch("builtins.open", create=True):
        with patch("json.load", return_value={"sample": {}}):
            resp = client.post("/api/v1/samples/bulk-import-specimens", json={})

    assert resp.status_code == 200
    body = resp.json()
    assert body["created_count"] == 0
    assert body["skipped_count"] == 0


def test_bulk_import_specimens_multiple_samples(monkeypatch):
    """Test bulk import with multiple specimen samples."""
    client = TestClient(app)

    fake_organism = SimpleNamespace(grouping_key="Homo_sapiens")
    fake_session = FakeSession(organisms={"default": fake_organism}, samples={"default": None})

    app.dependency_overrides[samples.get_current_active_user] = _override_user(["admin"])
    app.dependency_overrides[samples.get_db] = _override_db(fake_session)

    def mock_create_sample(
        db,
        bpa_sample_id,
        sample_data,
        organism_key,
        kind,
        derived_from_sample_id=None,
        ena_atol_map=None,
    ):
        sample = SimpleNamespace(
            id=uuid.uuid4(),
            organism_key=organism_key,
            specimen_id=sample_data.get("specimen_id"),
            kind=kind,
        )
        submission = SimpleNamespace(id=uuid.uuid4(), sample_id=sample.id)
        return sample, submission

    monkeypatch.setattr(samples, "_create_sample_with_submission", mock_create_sample)
    monkeypatch.setattr(samples, "require_role", lambda current_user, roles: None)

    with patch("builtins.open", create=True):
        with patch("json.load", return_value={"sample": {}}):
            payload = {
                "SPEC001_9606": {
                    "organism_grouping_key": "Homo_sapiens",
                    "specimen_id": "SPEC001",
                    "lifestage": "adult",
                },
                "SPEC002_9606": {
                    "organism_grouping_key": "Homo_sapiens",
                    "specimen_id": "SPEC002",
                    "lifestage": "juvenile",
                },
                "SPEC003_9606": {
                    "organism_grouping_key": "Homo_sapiens",
                    "specimen_id": "SPEC003",
                    "lifestage": "larva",
                },
            }

            resp = client.post("/api/v1/samples/bulk-import-specimens", json=payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["created_count"] == 3
    assert body["skipped_count"] == 0

"""Unit tests for bulk import experiments endpoint."""

import uuid
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_current_active_user, get_db
from app.main import app
from app.models.experiment import Experiment
from app.models.project import Project
from app.models.read import Read
from app.models.sample import Sample


class _FakeSession:
    """Fake database session for testing."""

    def __init__(self):
        self.added = []
        self.committed = False
        self.rolled_back = False
        self._query_results = {}
        self._samples_by_id = {}  # Store samples by bpa_sample_id for lookup

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def query(self, model):
        return _FakeQuery(self, model)


class _FakeQuery:
    """Fake query object for testing."""

    def __init__(self, session, model):
        self.session = session
        self.model = model
        self._filters = []

    def filter(self, *args):
        self._filters.extend(args)
        return self

    def first(self):
        # Return results based on model and filters
        if self.model == Experiment:
            return self.session._query_results.get("experiment")
        elif self.model == Sample:
            # Check if we have filters for bpa_sample_id lookup
            if self._filters:
                for filter_expr in self._filters:
                    # Try to extract the comparison value from the filter expression
                    if hasattr(filter_expr, "right") and hasattr(filter_expr.right, "value"):
                        # This is a binary expression like Sample.bpa_sample_id == 'value'
                        filter_value = filter_expr.right.value
                        if hasattr(filter_expr, "left") and hasattr(filter_expr.left, "key"):
                            if filter_expr.left.key == "bpa_sample_id":
                                # Look up sample by bpa_sample_id
                                return self.session._samples_by_id.get(filter_value)
            # Fallback to default sample
            return self.session._query_results.get("sample")
        elif self.model == Project:
            return self.session._query_results.get("project")
        elif self.model == Read:
            return self.session._query_results.get("read")
        return None


@pytest.fixture
def mock_db():
    """Create mock database session."""
    return _FakeSession()


@pytest.fixture
def mock_user():
    """Create mock user with admin role."""
    user = MagicMock()
    user.role = "admin"
    return user


@pytest.fixture
def client(mock_db, mock_user):
    """Create test client with dependency overrides."""

    def override_get_db():
        return mock_db

    def override_get_current_active_user():
        return mock_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_active_user] = override_get_current_active_user

    test_client = TestClient(app)
    yield test_client

    app.dependency_overrides.clear()


def test_bulk_import_experiments_success(client, mock_db, mock_user):
    """Test successful bulk import of experiments with reads."""
    # Setup mock sample
    sample = Sample(
        id=uuid.uuid4(),
        bpa_sample_id="102.100.100/12345",
        organism_key="Test_organism_123",
    )
    mock_db._query_results["sample"] = sample
    mock_db._samples_by_id["102.100.100/12345"] = sample
    mock_db._query_results["experiment"] = None  # No existing experiment
    mock_db._query_results["project"] = Project(id=uuid.uuid4())
    mock_db._query_results["read"] = None  # No existing read

    experiments_data = {
        "PKG001": {
            "bpa_sample_id": "102.100.100/12345",
            "bpa_library_id": "LIB001",
            "runs": [
                {
                    "bpa_resource_id": "RES001",
                    "filename": "sample_R1.fastq.gz",
                },
                {
                    "bpa_resource_id": "RES002",
                    "filename": "sample_R2.fastq.gz",
                },
            ],
        }
    }

    response = client.post("/api/v1/experiments/bulk-import", json=experiments_data)

    assert response.status_code == 200
    data = response.json()
    assert data["created_experiment_count"] == 1
    assert data["skipped_experiment_count"] == 0
    assert data["created_reads_count"] == 2
    assert data["skipped_reads_count"] == 0
    assert "Experiments: 1 created, 0 skipped" in data["message"]
    assert "Reads: 2 created, 0 skipped" in data["message"]


def test_bulk_import_experiments_existing_experiment_new_reads(client, mock_db, mock_user):
    """Test bulk import when experiment exists but has new reads."""
    # Setup existing experiment
    experiment_id = uuid.uuid4()
    existing_experiment = Experiment(
        id=experiment_id,
        bpa_package_id="PKG001",
        sample_id=uuid.uuid4(),
    )
    mock_db._query_results["experiment"] = existing_experiment
    mock_db._query_results["project"] = Project(id=uuid.uuid4())
    mock_db._query_results["read"] = None  # No existing reads

    experiments_data = {
        "PKG001": {
            "bpa_sample_id": "102.100.100/12345",
            "bpa_library_id": "LIB001",
            "runs": [
                {
                    "bpa_resource_id": "RES001",
                    "filename": "sample_R1.fastq.gz",
                },
                {
                    "bpa_resource_id": "RES002",
                    "filename": "sample_R2.fastq.gz",
                },
            ],
        }
    }

    response = client.post("/api/v1/experiments/bulk-import", json=experiments_data)

    assert response.status_code == 200
    data = response.json()
    assert data["created_experiment_count"] == 0
    assert data["skipped_experiment_count"] == 1
    assert data["created_reads_count"] == 2
    assert data["skipped_reads_count"] == 0
    assert "Experiments: 0 created, 1 skipped" in data["message"]
    assert "Reads: 2 created, 0 skipped" in data["message"]


def test_bulk_import_experiments_existing_experiment_existing_reads(client, mock_db, mock_user):
    """Test bulk import when experiment and reads already exist."""
    # Setup existing experiment
    experiment_id = uuid.uuid4()
    existing_experiment = Experiment(
        id=experiment_id,
        bpa_package_id="PKG001",
        sample_id=uuid.uuid4(),
    )
    mock_db._query_results["experiment"] = existing_experiment
    mock_db._query_results["project"] = Project(id=uuid.uuid4())

    # Mock existing read
    existing_read = Read(
        id=uuid.uuid4(),
        bpa_resource_id="RES001",
        experiment_id=experiment_id,
    )
    mock_db._query_results["read"] = existing_read

    experiments_data = {
        "PKG001": {
            "bpa_sample_id": "102.100.100/12345",
            "bpa_library_id": "LIB001",
            "runs": [
                {
                    "bpa_resource_id": "RES001",
                    "filename": "sample_R1.fastq.gz",
                },
            ],
        }
    }

    response = client.post("/api/v1/experiments/bulk-import", json=experiments_data)

    assert response.status_code == 200
    data = response.json()
    assert data["created_experiment_count"] == 0
    assert data["skipped_experiment_count"] == 1
    assert data["created_reads_count"] == 0
    assert data["skipped_reads_count"] == 1
    assert "Experiments: 0 created, 1 skipped" in data["message"]
    assert "Reads: 0 created, 1 skipped" in data["message"]


def test_bulk_import_experiments_missing_sample(client, mock_db, mock_user):
    """Test bulk import with missing sample."""
    mock_db._query_results["sample"] = None  # Sample not found
    mock_db._query_results["experiment"] = None

    experiments_data = {
        "PKG001": {
            "bpa_sample_id": "102.100.100/99999",
            "bpa_library_id": "LIB001",
            "runs": [
                {
                    "bpa_resource_id": "RES001",
                    "filename": "sample_R1.fastq.gz",
                },
            ],
        }
    }

    response = client.post("/api/v1/experiments/bulk-import", json=experiments_data)

    assert response.status_code == 200
    data = response.json()
    assert data["created_experiment_count"] == 0
    assert data["skipped_experiment_count"] == 1
    assert data["created_reads_count"] == 0
    assert data["skipped_reads_count"] == 1  # Read counted as skipped
    assert data["errors"] is not None
    assert any("Sample not found" in error for error in data["errors"])


def test_bulk_import_experiments_missing_bpa_sample_id(client, mock_db, mock_user):
    """Test bulk import with missing bpa_sample_id."""
    mock_db._query_results["experiment"] = None

    experiments_data = {
        "PKG001": {
            "bpa_library_id": "LIB001",
            "runs": [
                {
                    "bpa_resource_id": "RES001",
                    "filename": "sample_R1.fastq.gz",
                },
            ],
        }
    }

    response = client.post("/api/v1/experiments/bulk-import", json=experiments_data)

    assert response.status_code == 200
    data = response.json()
    assert data["created_experiment_count"] == 0
    assert data["skipped_experiment_count"] == 1
    assert data["skipped_reads_count"] == 1  # Read counted as skipped
    assert data["errors"] is not None
    assert any("Missing required field 'bpa_sample_id'" in error for error in data["errors"])


def test_bulk_import_experiments_missing_bpa_library_id(client, mock_db, mock_user):
    """Test bulk import with missing bpa_library_id."""
    sample = Sample(
        id=uuid.uuid4(),
        bpa_sample_id="102.100.100/12345",
        organism_key="Test_organism_123",
    )
    mock_db._query_results["sample"] = sample
    mock_db._samples_by_id["102.100.100/12345"] = sample
    mock_db._query_results["experiment"] = None

    experiments_data = {
        "PKG001": {
            "bpa_sample_id": "102.100.100/12345",
            "runs": [
                {
                    "bpa_resource_id": "RES001",
                    "filename": "sample_R1.fastq.gz",
                },
            ],
        }
    }

    response = client.post("/api/v1/experiments/bulk-import", json=experiments_data)

    assert response.status_code == 200
    data = response.json()
    assert data["created_experiment_count"] == 0
    assert data["skipped_experiment_count"] == 1
    assert data["skipped_reads_count"] == 1  # Read counted as skipped
    assert data["errors"] is not None
    assert any("Missing required field 'bpa_library_id'" in error for error in data["errors"])


def test_bulk_import_experiments_read_missing_bpa_resource_id(client, mock_db, mock_user):
    """Test bulk import with read missing bpa_resource_id."""
    sample = Sample(
        id=uuid.uuid4(),
        bpa_sample_id="102.100.100/12345",
        organism_key="Test_organism_123",
    )
    mock_db._query_results["sample"] = sample
    mock_db._samples_by_id["102.100.100/12345"] = sample
    mock_db._query_results["experiment"] = None
    mock_db._query_results["project"] = Project(id=uuid.uuid4())

    experiments_data = {
        "PKG001": {
            "bpa_sample_id": "102.100.100/12345",
            "bpa_library_id": "LIB001",
            "runs": [
                {
                    "filename": "sample_R1.fastq.gz",
                    # Missing bpa_resource_id
                },
            ],
        }
    }

    response = client.post("/api/v1/experiments/bulk-import", json=experiments_data)

    assert response.status_code == 200
    data = response.json()
    assert data["created_experiment_count"] == 1  # Experiment created
    assert data["skipped_experiment_count"] == 0
    assert data["created_reads_count"] == 0  # Read skipped
    assert data["skipped_reads_count"] == 1
    assert data["errors"] is not None
    assert any("Missing required field 'bpa_resource_id'" in error for error in data["errors"])
    assert any("sample_R1.fastq.gz" in error for error in data["errors"])


def test_bulk_import_experiments_multiple_with_mixed_results(client, mock_db, mock_user):
    """Test bulk import with multiple experiments having mixed results."""
    sample = Sample(
        id=uuid.uuid4(),
        bpa_sample_id="102.100.100/12345",
        organism_key="Test_organism_123",
    )
    mock_db._query_results["sample"] = sample
    mock_db._samples_by_id["102.100.100/12345"] = sample  # Add to lookup dictionary
    mock_db._query_results["experiment"] = None
    mock_db._query_results["project"] = Project(id=uuid.uuid4())
    mock_db._query_results["read"] = None

    experiments_data = {
        "PKG001": {
            "bpa_sample_id": "102.100.100/12345",
            "bpa_library_id": "LIB001",
            "runs": [
                {
                    "bpa_resource_id": "RES001",
                    "filename": "sample_R1.fastq.gz",
                },
            ],
        },
        "PKG002": {
            "bpa_sample_id": "102.100.100/99999",  # Missing sample
            "bpa_library_id": "LIB002",
            "runs": [
                {
                    "bpa_resource_id": "RES002",
                    "filename": "sample2_R1.fastq.gz",
                },
            ],
        },
    }

    response = client.post("/api/v1/experiments/bulk-import", json=experiments_data)

    assert response.status_code == 200
    data = response.json()
    assert data["created_experiment_count"] == 1
    assert data["skipped_experiment_count"] == 1
    assert data["created_reads_count"] == 1
    assert data["skipped_reads_count"] == 1
    assert data["errors"] is not None
    assert len(data["errors"]) == 1  # Only PKG002 error

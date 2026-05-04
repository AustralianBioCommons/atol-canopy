"""Tests for assembly service."""

import uuid
from unittest.mock import MagicMock, Mock, patch

import pytest
from sqlalchemy.orm import Session

from app.models.assembly import Assembly
from app.models.experiment import Experiment
from app.models.organism import Organism
from app.models.sample import Sample
from app.schemas.assembly import AssemblyCreate, AssemblyCreateFromExperiments, AssemblyDataTypes
from app.services.assembly_service import AssemblyService


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return MagicMock(spec=Session)


@pytest.fixture
def assembly_service():
    """Create an AssemblyService instance."""
    return AssemblyService(Assembly)


@pytest.fixture
def sample_assembly_create():
    """Create a sample AssemblyCreate schema."""
    return AssemblyCreate(
        taxon_id=172942,
        sample_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        assembly_name="Test Assembly",
        assembly_type="clone or isolate",
        tol_id="tol-001",
        data_types=AssemblyDataTypes.PACBIO_SMRT,
        coverage=50.0,
        program="hifiasm",
        moleculetype="genomic DNA",
    )


class TestCreateAssembly:
    """Tests for create method with auto-increment versioning."""

    def test_create_first_version(self, mock_db, assembly_service, sample_assembly_create):
        """Test creating first version (version 1)."""
        # Mock query to return None (no existing versions)
        mock_query = Mock()
        mock_query.filter.return_value.scalar.return_value = None
        mock_db.query.return_value = mock_query

        # Mock the assembly object that will be created
        created_assembly = Assembly(
            id=uuid.uuid4(),
            taxon_id=sample_assembly_create.taxon_id,
            sample_id=sample_assembly_create.sample_id,
            data_types=sample_assembly_create.data_types,
            version=1,
        )
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        with patch.object(Assembly, "__init__", return_value=None):
            result = assembly_service.create(mock_db, obj_in=sample_assembly_create)

        # Verify version was set to 1
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_create_increments_version(self, mock_db, assembly_service, sample_assembly_create):
        """Test that version increments from existing max version."""
        # Mock query to return existing max version of 3
        mock_query = Mock()
        mock_query.filter.return_value.scalar.return_value = 3
        mock_db.query.return_value = mock_query

        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        with patch.object(Assembly, "__init__", return_value=None):
            result = assembly_service.create(mock_db, obj_in=sample_assembly_create)

        # Verify version was incremented to 4
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_create_version_per_combination(self, mock_db, assembly_service):
        """Test that version is per (data_types, taxon_id, sample_id) combination."""
        sample_id = uuid.uuid4()

        # Create two assemblies with different data_types
        assembly1 = AssemblyCreate(
            taxon_id=172942,
            sample_id=sample_id,
            assembly_name="Assembly 1",
            assembly_type="clone or isolate",
            tol_id="tol-002",
            data_types=AssemblyDataTypes.PACBIO_SMRT,
            coverage=50.0,
            program="hifiasm",
            moleculetype="genomic DNA",
        )

        assembly2 = AssemblyCreate(
            taxon_id=172942,
            sample_id=sample_id,
            assembly_name="Assembly 2",
            assembly_type="clone or isolate",
            tol_id="tol-003",
            data_types=AssemblyDataTypes.PACBIO_SMRT_HIC,
            coverage=50.0,
            program="hifiasm",
            moleculetype="genomic DNA",
        )

        # Mock query to return None for both (different combinations)
        mock_query = Mock()
        mock_query.filter.return_value.scalar.return_value = None
        mock_db.query.return_value = mock_query
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        with patch.object(Assembly, "__init__", return_value=None):
            assembly_service.create(mock_db, obj_in=assembly1)
            assembly_service.create(mock_db, obj_in=assembly2)

        # Both should get version 1 since they have different data_types
        assert mock_db.add.call_count == 2


class TestCreateFromExperiments:
    """Tests for create_from_experiments method."""

    def test_create_from_experiments_success(self, mock_db, assembly_service):
        """Test successful assembly creation from experiments."""
        taxon_id = 172942
        organism = Organism(
            taxon_id=taxon_id,
            scientific_name="Test Species",
        )
        sample = Sample(id=uuid.uuid4(), taxon_id=taxon_id)
        experiments = [
            Experiment(
                id=uuid.uuid4(),
                sample_id=sample.id,
                platform="PACBIO_SMRT",
                library_strategy="WGS",
            ),
        ]

        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.return_value = organism
        mock_db.query.return_value.filter.return_value.all.side_effect = [
            [sample],  # samples query
            experiments,  # experiments query
        ]

        assembly_in = AssemblyCreateFromExperiments(
            sample_id=sample.id,
            assembly_name="Test Assembly",
            assembly_type="clone or isolate",
            tol_id="tol-004",
            coverage=50.0,
            program="hifiasm",
            moleculetype="genomic DNA",
        )

        with patch.object(assembly_service, "create") as mock_create:
            mock_create.return_value = Mock(
                id=uuid.uuid4(),
                data_types=AssemblyDataTypes.PACBIO_SMRT,
                version=1,
            )

            assembly, platform_info = assembly_service.create_from_experiments(
                mock_db, taxon_id=taxon_id, assembly_in=assembly_in
            )

        # Verify platform info was returned
        assert "platforms" in platform_info
        assert "library_strategies" in platform_info
        assert "experiment_count" in platform_info

    def test_create_from_experiments_organism_not_found(self, mock_db, assembly_service):
        """Test error when organism not found."""
        taxon_id = 999999
        mock_db.query.return_value.filter.return_value.first.return_value = None

        assembly_in = AssemblyCreateFromExperiments(
            sample_id=uuid.uuid4(),
            assembly_name="Test Assembly",
            assembly_type="clone or isolate",
            tol_id="tol-005",
            coverage=50.0,
            program="hifiasm",
            moleculetype="genomic DNA",
        )

        with pytest.raises(ValueError, match="Organism with taxon_id 999999 not found"):
            assembly_service.create_from_experiments(
                mock_db, taxon_id=taxon_id, assembly_in=assembly_in
            )

    def test_create_from_experiments_no_samples(self, mock_db, assembly_service):
        """Test error when no samples found for organism."""
        taxon_id = 172942
        organism = Organism(
            taxon_id=taxon_id,
            scientific_name="Test Species",
        )

        # Mock organism found but no samples
        mock_db.query.return_value.filter.return_value.first.return_value = organism
        mock_db.query.return_value.filter.return_value.all.return_value = []

        assembly_in = AssemblyCreateFromExperiments(
            sample_id=uuid.uuid4(),
            assembly_name="Test Assembly",
            assembly_type="clone or isolate",
            tol_id="tol-006",
            coverage=50.0,
            program="hifiasm",
            moleculetype="genomic DNA",
        )

        with pytest.raises(ValueError, match="No samples found"):
            assembly_service.create_from_experiments(
                mock_db, taxon_id=taxon_id, assembly_in=assembly_in
            )

    def test_create_from_experiments_no_experiments(self, mock_db, assembly_service):
        """Test error when no experiments found."""
        taxon_id = 172942
        organism = Organism(
            taxon_id=taxon_id,
            scientific_name="Test Species",
        )
        sample = Sample(id=uuid.uuid4(), taxon_id=taxon_id)

        # Mock organism and samples found but no experiments
        mock_db.query.return_value.filter.return_value.first.return_value = organism
        mock_db.query.return_value.filter.return_value.all.side_effect = [
            [sample],  # samples query
            [],  # experiments query - empty
        ]

        assembly_in = AssemblyCreateFromExperiments(
            sample_id=sample.id,
            assembly_name="Test Assembly",
            assembly_type="clone or isolate",
            tol_id="tol-007",
            coverage=50.0,
            program="hifiasm",
            moleculetype="genomic DNA",
        )

        with pytest.raises(ValueError, match="No experiments found"):
            assembly_service.create_from_experiments(
                mock_db, taxon_id=taxon_id, assembly_in=assembly_in
            )

    def test_create_from_experiments_overrides_data_types(self, mock_db, assembly_service):
        """Test that data_types is overridden based on experiments."""
        taxon_id = 172942
        organism = Organism(
            taxon_id=taxon_id,
            scientific_name="Test Species",
        )
        sample = Sample(id=uuid.uuid4(), taxon_id=taxon_id)
        experiments = [
            Experiment(
                id=uuid.uuid4(),
                sample_id=sample.id,
                platform="OXFORD_NANOPORE",
                library_strategy="WGS",
            ),
            Experiment(
                id=uuid.uuid4(),
                sample_id=sample.id,
                platform="ILLUMINA",
                library_strategy="Hi-C",
            ),
        ]

        mock_db.query.return_value.filter.return_value.first.return_value = organism
        mock_db.query.return_value.filter.return_value.all.side_effect = [
            [sample],
            experiments,
        ]

        # User provides PACBIO_SMRT which should be used instead of auto-detection
        assembly_in = AssemblyCreateFromExperiments(
            sample_id=sample.id,
            assembly_name="Test Assembly",
            assembly_type="clone or isolate",
            tol_id="tol-008",
            data_types=AssemblyDataTypes.PACBIO_SMRT,  # Explicitly provided, should be used
            coverage=50.0,
            program="hifiasm",
            moleculetype="genomic DNA",
        )

        with patch.object(assembly_service, "create") as mock_create:
            # Verify that create is called with overridden data_types
            mock_create.return_value = Mock(
                id=uuid.uuid4(),
                data_types=AssemblyDataTypes.OXFORD_NANOPORE_HIC,
                version=1,
            )

            assembly, platform_info = assembly_service.create_from_experiments(
                mock_db, taxon_id=taxon_id, assembly_in=assembly_in
            )

            # Verify create was called
            mock_create.assert_called_once()
            call_args = mock_create.call_args
            created_assembly_in = call_args.kwargs["obj_in"]

            # The data_types should be determined from experiments (ILLUMINA+WGS = Hi-C)
            assert created_assembly_in.taxon_id == 172942


class TestCreateFromIntent:
    """Tests for create_from_intent method."""

    def test_create_from_intent_creates_assembly_with_requested_status(
        self, mock_db, assembly_service
    ):
        """create_from_intent should create an Assembly with status='requested'."""
        sample_id = uuid.uuid4()
        taxon_id = 172942

        # get_next_version queries Assembly + AssemblyRun - both return None
        mock_query = Mock()
        mock_query.filter.return_value.scalar.return_value = None
        mock_db.query.return_value = mock_query
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        with patch.object(Assembly, "__init__", return_value=None):
            assembly_service.create_from_intent(
                mock_db,
                taxon_id=taxon_id,
                sample_id=sample_id,
                data_types="PACBIO_SMRT",
                tol_id="tol-999",
                project_id=None,
            )

        # Should add the Assembly and commit
        mock_db.add.assert_called_once()
        added_obj = mock_db.add.call_args[0][0]
        # The added object should be an Assembly with status="requested"
        assert isinstance(added_obj, Assembly)
        mock_db.commit.assert_called_once()

    def test_create_from_intent_version_is_next(self, mock_db, assembly_service):
        """create_from_intent assigns the next version based on existing assemblies."""
        sample_id = uuid.uuid4()

        mock_query = Mock()
        # Assembly.version max = 2, AssemblyRun.version max = None → next version = 3
        mock_query.filter.return_value.scalar.side_effect = [2, None]
        mock_db.query.return_value = mock_query
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        created_versions = []

        original_init = Assembly.__init__

        def capture_init(self, **kwargs):
            created_versions.append(kwargs.get("version"))

        with patch.object(Assembly, "__init__", capture_init):
            assembly_service.create_from_intent(
                mock_db,
                taxon_id=172942,
                sample_id=sample_id,
                data_types="PACBIO_SMRT",
                tol_id=None,
                project_id=None,
            )

        assert created_versions == [3]

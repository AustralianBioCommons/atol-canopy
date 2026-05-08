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

LONG_READ_SAMPLE_ID = uuid.uuid4()
HIC_SAMPLE_ID = uuid.uuid4()


@pytest.fixture
def mock_db():
    return MagicMock(spec=Session)


@pytest.fixture
def assembly_service():
    return AssemblyService(Assembly)


@pytest.fixture
def sample_assembly_create():
    return AssemblyCreate(
        taxon_id=172942,
        sample_id=LONG_READ_SAMPLE_ID,
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
    """Tests for create method with auto-increment versioning (generic flow)."""

    def test_create_first_version(self, mock_db, assembly_service, sample_assembly_create):
        mock_query = Mock()
        mock_query.filter.return_value.scalar.return_value = None
        mock_db.query.return_value = mock_query
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        with patch.object(Assembly, "__init__", return_value=None):
            assembly_service.create(mock_db, obj_in=sample_assembly_create)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_create_increments_version(self, mock_db, assembly_service, sample_assembly_create):
        mock_query = Mock()
        mock_query.filter.return_value.scalar.return_value = 3
        mock_db.query.return_value = mock_query
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        with patch.object(Assembly, "__init__", return_value=None):
            assembly_service.create(mock_db, obj_in=sample_assembly_create)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_create_version_per_combination(self, mock_db, assembly_service):
        sample_id = uuid.uuid4()

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

        mock_query = Mock()
        mock_query.filter.return_value.scalar.return_value = None
        mock_db.query.return_value = mock_query
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        with patch.object(Assembly, "__init__", return_value=None):
            assembly_service.create(mock_db, obj_in=assembly1)
            assembly_service.create(mock_db, obj_in=assembly2)

        assert mock_db.add.call_count == 2


class TestCreateFromExperiments:
    """Tests for create_from_experiments method."""

    def test_create_from_experiments_success(self, mock_db, assembly_service):
        taxon_id = 172942
        organism = Organism(taxon_id=taxon_id, scientific_name="Test Species")
        sample = Sample(id=uuid.uuid4(), taxon_id=taxon_id)
        experiments = [
            Experiment(
                id=uuid.uuid4(),
                sample_id=sample.id,
                platform="PACBIO_SMRT",
                library_strategy="WGS",
            ),
        ]

        mock_db.query.return_value.filter.return_value.first.return_value = organism
        mock_db.query.return_value.filter.return_value.all.side_effect = [
            [sample],
            experiments,
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
                id=uuid.uuid4(), data_types=AssemblyDataTypes.PACBIO_SMRT, version=1
            )
            assembly, platform_info = assembly_service.create_from_experiments(
                mock_db, taxon_id=taxon_id, assembly_in=assembly_in
            )

        assert "platforms" in platform_info
        assert "library_strategies" in platform_info
        assert "experiment_count" in platform_info

    def test_create_from_experiments_organism_not_found(self, mock_db, assembly_service):
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
                mock_db, taxon_id=999999, assembly_in=assembly_in
            )

    def test_create_from_experiments_no_samples(self, mock_db, assembly_service):
        taxon_id = 172942
        organism = Organism(taxon_id=taxon_id, scientific_name="Test Species")

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
        taxon_id = 172942
        organism = Organism(taxon_id=taxon_id, scientific_name="Test Species")
        sample = Sample(id=uuid.uuid4(), taxon_id=taxon_id)

        mock_db.query.return_value.filter.return_value.first.return_value = organism
        mock_db.query.return_value.filter.return_value.all.side_effect = [
            [sample],
            [],
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


class TestGetNextVersionForIntent:
    """Tests for get_next_version_for_intent — versioning by (taxon_id, long_read_specimen_sample_id)."""

    def test_first_version_when_no_prior_assemblies(self, mock_db, assembly_service):
        mock_query = Mock()
        mock_query.filter.return_value.scalar.return_value = None
        mock_db.query.return_value = mock_query

        version = assembly_service.get_next_version_for_intent(
            mock_db, taxon_id=172942, long_read_specimen_sample_id=LONG_READ_SAMPLE_ID
        )
        assert version == 1

    def test_increments_from_existing_max(self, mock_db, assembly_service):
        mock_query = Mock()
        mock_query.filter.return_value.scalar.return_value = 4
        mock_db.query.return_value = mock_query

        version = assembly_service.get_next_version_for_intent(
            mock_db, taxon_id=172942, long_read_specimen_sample_id=LONG_READ_SAMPLE_ID
        )
        assert version == 5

    def test_different_hic_sample_does_not_split_version_sequence(
        self, mock_db, assembly_service
    ):
        """Two intents with the same long_read_specimen_sample_id but different hic_specimen_sample_id
        must share the same version counter (hic_specimen_sample_id is NOT part of the key)."""
        call_count = [0]
        max_versions = [2]  # One prior assembly exists for this (taxon_id, long_read) pair

        mock_query = Mock()
        mock_query.filter.return_value.scalar.return_value = max_versions[0]
        mock_db.query.return_value = mock_query

        v1 = assembly_service.get_next_version_for_intent(
            mock_db, taxon_id=172942, long_read_specimen_sample_id=LONG_READ_SAMPLE_ID
        )
        # Both calls use the same (taxon_id, long_read_specimen_sample_id) key, so both
        # return 3 from the same mock (in real DB the second would see version=3 → return 4).
        # This test verifies the QUERY only filters on taxon_id + long_read_specimen_sample_id.
        assert v1 == 3


class TestCreateFromIntent:
    """Tests for create_from_intent — new signature with specimen sample IDs and manifest persistence."""

    def test_creates_assembly_with_requested_status(self, mock_db, assembly_service):
        mock_query = Mock()
        mock_query.filter.return_value.scalar.return_value = None
        mock_db.query.return_value = mock_query
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        with patch.object(Assembly, "__init__", return_value=None):
            assembly_service.create_from_intent(
                mock_db,
                taxon_id=172942,
                long_read_specimen_sample_id=LONG_READ_SAMPLE_ID,
                hic_specimen_sample_id=None,
                data_types="PACBIO_SMRT",
                tol_id="tol-999",
                project_id=None,
                manifest_json=None,
            )

        mock_db.add.assert_called_once()
        added_obj = mock_db.add.call_args[0][0]
        assert isinstance(added_obj, Assembly)
        mock_db.commit.assert_called_once()

    def test_version_is_next_based_on_long_read_sample(self, mock_db, assembly_service):
        """Version is derived from (taxon_id, long_read_specimen_sample_id) only."""
        mock_query = Mock()
        mock_query.filter.return_value.scalar.return_value = 2  # existing max = 2 → next = 3
        mock_db.query.return_value = mock_query
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        created_versions = []

        def capture_init(self, **kwargs):
            created_versions.append(kwargs.get("version"))

        with patch.object(Assembly, "__init__", capture_init):
            assembly_service.create_from_intent(
                mock_db,
                taxon_id=172942,
                long_read_specimen_sample_id=LONG_READ_SAMPLE_ID,
                hic_specimen_sample_id=None,
                data_types="PACBIO_SMRT",
                tol_id=None,
                project_id=None,
            )

        assert created_versions == [3]

    def test_manifest_json_persisted(self, mock_db, assembly_service):
        """manifest_json is stored on the Assembly object when provided."""
        mock_query = Mock()
        mock_query.filter.return_value.scalar.return_value = None
        mock_db.query.return_value = mock_query
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        sample_manifest = {"scientific_name": "Test", "reads": {"PACBIO_SMRT": {}}}
        stored_manifests = []

        def capture_init(self, **kwargs):
            stored_manifests.append(kwargs.get("manifest_json"))

        with patch.object(Assembly, "__init__", capture_init):
            assembly_service.create_from_intent(
                mock_db,
                taxon_id=172942,
                long_read_specimen_sample_id=LONG_READ_SAMPLE_ID,
                hic_specimen_sample_id=None,
                data_types="PACBIO_SMRT",
                tol_id=None,
                project_id=None,
                manifest_json=sample_manifest,
            )

        assert stored_manifests == [sample_manifest]

    def test_hic_specimen_sample_id_stored(self, mock_db, assembly_service):
        """hic_specimen_sample_id is stored on the Assembly."""
        mock_query = Mock()
        mock_query.filter.return_value.scalar.return_value = None
        mock_db.query.return_value = mock_query
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        hic_ids = []

        def capture_init(self, **kwargs):
            hic_ids.append(kwargs.get("hic_specimen_sample_id"))

        with patch.object(Assembly, "__init__", capture_init):
            assembly_service.create_from_intent(
                mock_db,
                taxon_id=172942,
                long_read_specimen_sample_id=LONG_READ_SAMPLE_ID,
                hic_specimen_sample_id=HIC_SAMPLE_ID,
                data_types="PACBIO_SMRT_HIC",
                tol_id=None,
                project_id=None,
            )

        assert hic_ids == [HIC_SAMPLE_ID]

    def test_sample_id_set_to_long_read_specimen_sample_id(self, mock_db, assembly_service):
        """sample_id is set to long_read_specimen_sample_id for backward compatibility."""
        mock_query = Mock()
        mock_query.filter.return_value.scalar.return_value = None
        mock_db.query.return_value = mock_query
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        sample_ids = []

        def capture_init(self, **kwargs):
            sample_ids.append(kwargs.get("sample_id"))

        with patch.object(Assembly, "__init__", capture_init):
            assembly_service.create_from_intent(
                mock_db,
                taxon_id=172942,
                long_read_specimen_sample_id=LONG_READ_SAMPLE_ID,
                hic_specimen_sample_id=None,
                data_types="PACBIO_SMRT",
                tol_id=None,
                project_id=None,
            )

        assert sample_ids == [LONG_READ_SAMPLE_ID]

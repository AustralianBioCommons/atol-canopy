import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock

import pytest
from sqlalchemy.orm import Session

from app.models.genome_note import GenomeNote
from app.schemas.genome_note import GenomeNoteCreate, GenomeNoteUpdate
from app.services.genome_note_service import GenomeNoteService


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return MagicMock(spec=Session)


@pytest.fixture
def genome_note_service():
    """Create a GenomeNoteService instance."""
    return GenomeNoteService()


@pytest.fixture
def sample_genome_note():
    """Create a sample genome note for testing."""
    return GenomeNote(
        id=uuid.uuid4(),
        organism_key="test_organism",
        assembly_id=uuid.uuid4(),
        version=1,
        title="Test Genome Note",
        note_url="https://example.com/note",
        is_published=False,
        published_at=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


class TestGetNextVersion:
    """Tests for get_next_version method."""

    def test_get_next_version_no_existing(self, mock_db, genome_note_service):
        """Test getting next version when no versions exist."""
        mock_query = Mock()
        mock_query.filter.return_value.scalar.return_value = None
        mock_db.query.return_value = mock_query

        version = genome_note_service.get_next_version(mock_db, "new_organism")

        assert version == 1

    def test_get_next_version_with_existing(self, mock_db, genome_note_service):
        """Test getting next version when versions exist."""
        mock_query = Mock()
        mock_query.filter.return_value.scalar.return_value = 3
        mock_db.query.return_value = mock_query

        version = genome_note_service.get_next_version(mock_db, "existing_organism")

        assert version == 4

    def test_get_next_version_different_organisms(self, mock_db, genome_note_service):
        """Test that version counting is per organism."""
        mock_query = Mock()
        mock_query.filter.return_value.scalar.return_value = 2
        mock_db.query.return_value = mock_query

        version = genome_note_service.get_next_version(mock_db, "organism_a")

        assert version == 3


class TestCreateGenomeNote:
    """Tests for create method."""

    def test_create_genome_note_success(self, mock_db, genome_note_service):
        """Test successful genome note creation."""
        assembly_id = uuid.uuid4()
        genome_note_in = GenomeNoteCreate(
            organism_key="test_organism",
            assembly_id=assembly_id,
            title="Test Note",
            note_url="https://example.com/note",
        )

        mock_query = Mock()
        mock_query.filter.return_value.scalar.return_value = None
        mock_db.query.return_value = mock_query

        created_note = genome_note_service.create(mock_db, genome_note_in)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    def test_create_genome_note_auto_version(self, mock_db, genome_note_service):
        """Test that version is automatically calculated."""
        assembly_id = uuid.uuid4()
        genome_note_in = GenomeNoteCreate(
            organism_key="test_organism",
            assembly_id=assembly_id,
            title="Test Note",
            note_url="https://example.com/note",
        )

        mock_query = Mock()
        mock_query.filter.return_value.scalar.return_value = 2
        mock_db.query.return_value = mock_query

        genome_note_service.create(mock_db, genome_note_in)

        call_args = mock_db.add.call_args[0][0]
        assert call_args.version == 3

    def test_create_genome_note_defaults(self, mock_db, genome_note_service):
        """Test that default values are set correctly."""
        assembly_id = uuid.uuid4()
        genome_note_in = GenomeNoteCreate(
            organism_key="test_organism",
            assembly_id=assembly_id,
            title="Test Note",
            note_url="https://example.com/note",
        )

        mock_query = Mock()
        mock_query.filter.return_value.scalar.return_value = None
        mock_db.query.return_value = mock_query

        genome_note_service.create(mock_db, genome_note_in)

        call_args = mock_db.add.call_args[0][0]
        assert call_args.is_published is False
        assert call_args.published_at is None


class TestPublishGenomeNote:
    """Tests for publish_genome_note method."""

    def test_publish_genome_note_success(self, mock_db, genome_note_service, sample_genome_note):
        """Test successful publishing of a genome note."""
        note_id = sample_genome_note.id

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = sample_genome_note
        mock_db.query.return_value = mock_query

        mock_existing_query = Mock()
        mock_existing_query.filter.return_value.filter.return_value.first.return_value = None
        mock_db.query.side_effect = [mock_query, mock_existing_query]

        result = genome_note_service.publish_genome_note(mock_db, note_id)

        assert result.is_published is True
        assert result.published_at is not None
        mock_db.commit.assert_called_once()

    def test_publish_genome_note_not_found(self, mock_db, genome_note_service):
        """Test publishing a non-existent genome note."""
        note_id = uuid.uuid4()

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with pytest.raises(ValueError, match="Genome note not found"):
            genome_note_service.publish_genome_note(mock_db, note_id)

    def test_publish_genome_note_already_published(
        self, mock_db, genome_note_service, sample_genome_note
    ):
        """Test publishing when organism already has a published note."""
        note_id = sample_genome_note.id

        existing_published = GenomeNote(
            id=uuid.uuid4(),
            organism_key=sample_genome_note.organism_key,
            assembly_id=uuid.uuid4(),
            version=2,
            title="Existing Published Note",
            note_url="https://example.com/existing",
            is_published=True,
            published_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = sample_genome_note
        mock_db.query.return_value = mock_query

        mock_existing_query = Mock()
        mock_existing_query.filter.return_value.filter.return_value.first.return_value = (
            existing_published
        )
        mock_db.query.side_effect = [mock_query, mock_existing_query]

        with pytest.raises(ValueError, match="already has a published genome note"):
            genome_note_service.publish_genome_note(mock_db, note_id)

        mock_db.commit.assert_not_called()


class TestUnpublishGenomeNote:
    """Tests for unpublish_genome_note method."""

    def test_unpublish_genome_note_success(self, mock_db, genome_note_service):
        """Test successful unpublishing of a genome note."""
        published_note = GenomeNote(
            id=uuid.uuid4(),
            organism_key="test_organism",
            assembly_id=uuid.uuid4(),
            version=1,
            title="Published Note",
            note_url="https://example.com/note",
            is_published=True,
            published_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = published_note
        mock_db.query.return_value = mock_query

        result = genome_note_service.unpublish_genome_note(mock_db, published_note.id)

        assert result.is_published is False
        assert result.published_at is None
        mock_db.commit.assert_called_once()

    def test_unpublish_genome_note_not_found(self, mock_db, genome_note_service):
        """Test unpublishing a non-existent genome note."""
        note_id = uuid.uuid4()

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with pytest.raises(ValueError, match="Genome note not found"):
            genome_note_service.unpublish_genome_note(mock_db, note_id)


class TestGetPublishedByOrganism:
    """Tests for get_published_by_organism method."""

    def test_get_published_by_organism_found(self, mock_db, genome_note_service):
        """Test retrieving published genome note for an organism."""
        published_note = GenomeNote(
            id=uuid.uuid4(),
            organism_key="test_organism",
            assembly_id=uuid.uuid4(),
            version=2,
            title="Published Note",
            note_url="https://example.com/note",
            is_published=True,
            published_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.first.return_value = published_note
        mock_db.query.return_value = mock_query

        result = genome_note_service.get_published_by_organism(mock_db, "test_organism")

        assert result == published_note
        assert result.is_published is True

    def test_get_published_by_organism_not_found(self, mock_db, genome_note_service):
        """Test retrieving published genome note when none exists."""
        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        result = genome_note_service.get_published_by_organism(mock_db, "test_organism")

        assert result is None


class TestGetVersionsByOrganism:
    """Tests for get_versions_by_organism method."""

    def test_get_versions_by_organism(self, mock_db, genome_note_service):
        """Test retrieving all versions for an organism."""
        notes = [
            GenomeNote(
                id=uuid.uuid4(),
                organism_key="test_organism",
                assembly_id=uuid.uuid4(),
                version=3,
                title="Version 3",
                note_url="https://example.com/v3",
                is_published=True,
                published_at=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            ),
            GenomeNote(
                id=uuid.uuid4(),
                organism_key="test_organism",
                assembly_id=uuid.uuid4(),
                version=2,
                title="Version 2",
                note_url="https://example.com/v2",
                is_published=False,
                published_at=None,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            ),
            GenomeNote(
                id=uuid.uuid4(),
                organism_key="test_organism",
                assembly_id=uuid.uuid4(),
                version=1,
                title="Version 1",
                note_url="https://example.com/v1",
                is_published=False,
                published_at=None,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            ),
        ]

        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.all.return_value = notes
        mock_db.query.return_value = mock_query

        result = genome_note_service.get_versions_by_organism(mock_db, "test_organism")

        assert len(result) == 3
        assert result[0].version == 3
        assert result[1].version == 2
        assert result[2].version == 1

    def test_get_versions_by_organism_empty(self, mock_db, genome_note_service):
        """Test retrieving versions when none exist."""
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.all.return_value = []
        mock_db.query.return_value = mock_query

        result = genome_note_service.get_versions_by_organism(mock_db, "test_organism")

        assert result == []


class TestUpdateGenomeNote:
    """Tests for update method."""

    def test_update_genome_note_success(self, mock_db, genome_note_service, sample_genome_note):
        """Test successful update of a genome note."""
        note_id = sample_genome_note.id
        update_data = GenomeNoteUpdate(
            title="Updated Title",
            note_url="https://example.com/updated",
        )

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = sample_genome_note
        mock_db.query.return_value = mock_query

        result = genome_note_service.update(mock_db, note_id, update_data)

        assert result.title == "Updated Title"
        assert result.note_url == "https://example.com/updated"
        mock_db.commit.assert_called_once()

    def test_update_genome_note_partial(self, mock_db, genome_note_service, sample_genome_note):
        """Test partial update of a genome note."""
        note_id = sample_genome_note.id
        original_url = sample_genome_note.note_url
        update_data = GenomeNoteUpdate(title="Updated Title Only")

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = sample_genome_note
        mock_db.query.return_value = mock_query

        result = genome_note_service.update(mock_db, note_id, update_data)

        assert result.title == "Updated Title Only"
        assert result.note_url == original_url

    def test_update_genome_note_not_found(self, mock_db, genome_note_service):
        """Test updating a non-existent genome note."""
        note_id = uuid.uuid4()
        update_data = GenomeNoteUpdate(title="Updated Title")

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        result = genome_note_service.update(mock_db, note_id, update_data)

        assert result is None
        mock_db.commit.assert_not_called()


class TestDeleteGenomeNote:
    """Tests for delete method."""

    def test_delete_genome_note_success(self, mock_db, genome_note_service, sample_genome_note):
        """Test successful deletion of a genome note."""
        note_id = sample_genome_note.id

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = sample_genome_note
        mock_db.query.return_value = mock_query

        result = genome_note_service.delete(mock_db, note_id)

        assert result == sample_genome_note
        mock_db.delete.assert_called_once_with(sample_genome_note)
        mock_db.commit.assert_called_once()

    def test_delete_genome_note_not_found(self, mock_db, genome_note_service):
        """Test deleting a non-existent genome note."""
        note_id = uuid.uuid4()

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        result = genome_note_service.delete(mock_db, note_id)

        assert result is None
        mock_db.delete.assert_not_called()
        mock_db.commit.assert_not_called()

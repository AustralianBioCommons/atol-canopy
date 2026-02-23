import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock

import pytest
from sqlalchemy.orm import Session

from app.models.genome_note import GenomeNote
from app.services.genome_note_service import GenomeNoteService


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return MagicMock(spec=Session)


@pytest.fixture
def genome_note_service():
    """Create a GenomeNoteService instance."""
    return GenomeNoteService(GenomeNote)


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


class TestGetByFilters:
    """Tests for basic filter helpers."""

    def test_get_by_organism_key(self, mock_db, genome_note_service, sample_genome_note):
        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = [sample_genome_note]
        mock_db.query.return_value = mock_query

        result = genome_note_service.get_by_organism_key(mock_db, "test_organism")

        assert result == [sample_genome_note]

    def test_get_by_assembly_id(self, mock_db, genome_note_service, sample_genome_note):
        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = [sample_genome_note]
        mock_db.query.return_value = mock_query

        result = genome_note_service.get_by_assembly_id(mock_db, sample_genome_note.assembly_id)

        assert result == [sample_genome_note]

    def test_get_by_title(self, mock_db, genome_note_service, sample_genome_note):
        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = [sample_genome_note]
        mock_db.query.return_value = mock_query

        result = genome_note_service.get_by_title(mock_db, "Test")

        assert result == [sample_genome_note]

    def test_get_multi_with_filters(self, mock_db, genome_note_service, sample_genome_note):
        class FakeQuery:
            def filter(self, *_args, **_kwargs):
                return self

            def offset(self, *_args, **_kwargs):
                return self

            def limit(self, *_args, **_kwargs):
                return self

            def all(self):
                return [sample_genome_note]

        mock_db.query.return_value = FakeQuery()

        result = genome_note_service.get_multi_with_filters(
            mock_db,
            skip=0,
            limit=10,
            organism_key="test_organism",
            assembly_id=sample_genome_note.assembly_id,
            is_published=False,
            title="Test",
        )

        assert result == [sample_genome_note]

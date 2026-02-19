from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.genome_note import GenomeNote
from app.schemas.genome_note import GenomeNoteCreate, GenomeNoteUpdate
from app.services.base_service import BaseService


class GenomeNoteService(BaseService[GenomeNote, GenomeNoteCreate, GenomeNoteUpdate]):
    """Service for GenomeNote operations with version management."""

    def get_by_organism_key(self, db: Session, organism_key: str) -> List[GenomeNote]:
        """Get all genome notes for an organism."""
        return db.query(GenomeNote).filter(GenomeNote.organism_key == organism_key).all()

    def get_by_assembly_id(self, db: Session, assembly_id: UUID) -> List[GenomeNote]:
        """Get genome notes by assembly ID."""
        return db.query(GenomeNote).filter(GenomeNote.assembly_id == assembly_id).all()

    def get_by_title(self, db: Session, title: str) -> List[GenomeNote]:
        """Get genome notes by title (case-insensitive search)."""
        return db.query(GenomeNote).filter(GenomeNote.title.ilike(f"%{title}%")).all()

    def get_published_notes(self, db: Session) -> List[GenomeNote]:
        """Get all published genome notes."""
        return db.query(GenomeNote).filter(GenomeNote.is_published == True).all()

    def get_published_by_organism(self, db: Session, organism_key: str) -> Optional[GenomeNote]:
        """Get the published genome note for a specific organism."""
        return (
            db.query(GenomeNote)
            .filter(GenomeNote.organism_key == organism_key)
            .filter(GenomeNote.is_published == True)
            .first()
        )

    def get_versions_by_organism(self, db: Session, organism_key: str) -> List[GenomeNote]:
        """Get all versions of genome notes for an organism, ordered by version descending."""
        return (
            db.query(GenomeNote)
            .filter(GenomeNote.organism_key == organism_key)
            .order_by(GenomeNote.version.desc())
            .all()
        )

    def get_next_version(self, db: Session, organism_key: str) -> int:
        """Calculate the next version number for an organism's genome notes."""
        max_version = (
            db.query(func.max(GenomeNote.version))
            .filter(GenomeNote.organism_key == organism_key)
            .scalar()
        )
        return (max_version or 0) + 1

    def publish_genome_note(self, db: Session, genome_note_id: UUID) -> GenomeNote:
        """
        Publish a genome note.

        Raises ValueError if the organism already has a published genome note.
        Use unpublish_genome_note first to unpublish the existing note.
        """
        note = db.query(GenomeNote).filter(GenomeNote.id == genome_note_id).first()
        if not note:
            raise ValueError("Genome note not found")

        # Check if organism already has a published note
        existing_published = (
            db.query(GenomeNote)
            .filter(GenomeNote.organism_key == note.organism_key)
            .filter(GenomeNote.is_published == True)
            .first()
        )

        if existing_published:
            raise ValueError(
                f"Organism '{note.organism_key}' already has a published genome note "
                f"(version {existing_published.version}). Please unpublish it first."
            )

        # Publish this note
        note.is_published = True
        note.published_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(note)
        return note

    def unpublish_genome_note(self, db: Session, genome_note_id: UUID) -> GenomeNote:
        """Unpublish a genome note."""
        note = db.query(GenomeNote).filter(GenomeNote.id == genome_note_id).first()
        if not note:
            raise ValueError("Genome note not found")

        note.is_published = False
        note.published_at = None
        db.commit()
        db.refresh(note)
        return note

    def get_multi_with_filters(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        organism_key: Optional[str] = None,
        assembly_id: Optional[UUID] = None,
        is_published: Optional[bool] = None,
        title: Optional[str] = None,
    ) -> List[GenomeNote]:
        """Get genome notes with filters."""
        query = db.query(GenomeNote)
        if organism_key:
            query = query.filter(GenomeNote.organism_key == organism_key)
        if assembly_id:
            query = query.filter(GenomeNote.assembly_id == assembly_id)
        if is_published is not None:
            query = query.filter(GenomeNote.is_published == is_published)
        if title:
            query = query.filter(GenomeNote.title.ilike(f"%{title}%"))
        return query.offset(skip).limit(limit).all()


genome_note_service = GenomeNoteService(GenomeNote)

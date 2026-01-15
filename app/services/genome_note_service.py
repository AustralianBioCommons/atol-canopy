from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.genome_note import GenomeNote, GenomeNoteAssembly
from app.schemas.genome_note import GenomeNoteAssemblyCreate, GenomeNoteCreate, GenomeNoteUpdate
from app.services.base_service import BaseService


class GenomeNoteService(BaseService[GenomeNote, GenomeNoteCreate, GenomeNoteUpdate]):
    """Service for GenomeNote operations."""

    def get_by_organism_key(self, db: Session, organism_key: str) -> List[GenomeNote]:
        """Get genome notes by organism key."""
        return db.query(GenomeNote).filter(GenomeNote.organism_key == organism_key).all()

    def get_by_title(self, db: Session, title: str) -> List[GenomeNote]:
        """Get genome notes by title."""
        return db.query(GenomeNote).filter(GenomeNote.title.ilike(f"%{title}%")).all()

    def get_published_notes(self, db: Session) -> List[GenomeNote]:
        """Get all published genome notes."""
        return db.query(GenomeNote).filter(GenomeNote.is_published == True).all()

    def get_multi_with_filters(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        organism_key: Optional[str] = None,
        is_published: Optional[bool] = None,
        title: Optional[str] = None,
    ) -> List[GenomeNote]:
        """Get genome notes with filters."""
        query = db.query(GenomeNote)
        if organism_key:
            query = query.filter(GenomeNote.organism_key == organism_key)
        if is_published is not None:
            query = query.filter(GenomeNote.is_published == is_published)
        if title:
            query = query.filter(GenomeNote.title.ilike(f"%{title}%"))
        return query.offset(skip).limit(limit).all()


class GenomeNoteAssemblyService(
    BaseService[GenomeNoteAssembly, GenomeNoteAssemblyCreate, GenomeNoteAssemblyCreate]
):
    """Service for GenomeNoteAssembly operations."""

    def get_by_genome_note_id(self, db: Session, genome_note_id: UUID) -> List[GenomeNoteAssembly]:
        """Get genome note-assembly relationships by genome note ID."""
        return (
            db.query(GenomeNoteAssembly)
            .filter(GenomeNoteAssembly.genome_note_id == genome_note_id)
            .all()
        )

    def get_by_assembly_id(self, db: Session, assembly_id: UUID) -> List[GenomeNoteAssembly]:
        """Get genome note-assembly relationships by assembly ID."""
        return (
            db.query(GenomeNoteAssembly).filter(GenomeNoteAssembly.assembly_id == assembly_id).all()
        )


genome_note_service = GenomeNoteService(GenomeNote)
genome_note_assembly_service = GenomeNoteAssemblyService(GenomeNoteAssembly)

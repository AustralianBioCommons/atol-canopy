from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_active_user, get_db
from app.core.pagination import Pagination, pagination_params
from app.core.policy import policy
from app.models.genome_note import GenomeNote
from app.models.user import User
from app.schemas.genome_note import (
    GenomeNote as GenomeNoteSchema,
)
from app.schemas.genome_note import (
    GenomeNoteCreate,
    GenomeNoteUpdate,
)
from app.services.genome_note_service import genome_note_service

router = APIRouter()


@router.get("/", response_model=List[GenomeNoteSchema])
def read_genome_notes(
    db: Session = Depends(get_db),
    pagination: Pagination = Depends(pagination_params),
    organism_key: Optional[str] = Query(None, description="Filter by organism key"),
    assembly_id: Optional[UUID] = Query(None, description="Filter by assembly ID"),
    is_published: Optional[bool] = Query(None, description="Filter by publication status"),
    title: Optional[str] = Query(None, description="Filter by title (case-insensitive)"),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Retrieve genome notes with optional filters.
    """
    genome_notes = genome_note_service.get_multi_with_filters(
        db,
        skip=pagination.offset,
        limit=pagination.limit,
        organism_key=organism_key,
        assembly_id=assembly_id,
        is_published=is_published,
        title=title,
    )
    return genome_notes


@router.post("/", response_model=GenomeNoteSchema)
@policy("genome_notes:write")
def create_genome_note(
    *,
    db: Session = Depends(get_db),
    genome_note_in: GenomeNoteCreate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Create new genome note with auto-incremented version.

    The version number is automatically calculated based on existing versions
    for the organism. The note is created in draft status (is_published=False).
    """
    # Auto-calculate next version for this organism
    next_version = genome_note_service.get_next_version(db, genome_note_in.organism_key)

    genome_note = GenomeNote(
        organism_key=genome_note_in.organism_key,
        assembly_id=genome_note_in.assembly_id,
        version=next_version,
        title=genome_note_in.title,
        note_url=genome_note_in.note_url,
        is_published=False,
    )
    db.add(genome_note)
    db.commit()
    db.refresh(genome_note)
    return genome_note


@router.get("/{genome_note_id}", response_model=GenomeNoteSchema)
def read_genome_note(
    *,
    db: Session = Depends(get_db),
    genome_note_id: UUID,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get genome note by ID.
    """
    genome_note = db.query(GenomeNote).filter(GenomeNote.id == genome_note_id).first()
    if not genome_note:
        raise HTTPException(status_code=404, detail="Genome note not found")
    return genome_note


@router.put("/{genome_note_id}", response_model=GenomeNoteSchema)
@policy("genome_notes:write")
def update_genome_note(
    *,
    db: Session = Depends(get_db),
    genome_note_id: UUID,
    genome_note_in: GenomeNoteUpdate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Update a genome note.

    Only title and note_url can be updated. Version and publication status
    cannot be changed through this endpoint.
    """
    genome_note = db.query(GenomeNote).filter(GenomeNote.id == genome_note_id).first()
    if not genome_note:
        raise HTTPException(status_code=404, detail="Genome note not found")

    update_data = genome_note_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(genome_note, field, value)

    db.add(genome_note)
    db.commit()
    db.refresh(genome_note)
    return genome_note


@router.delete("/{genome_note_id}", response_model=GenomeNoteSchema)
@policy("genome_notes:write")
def delete_genome_note(
    *,
    db: Session = Depends(get_db),
    genome_note_id: UUID,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Delete a genome note.

    """
    genome_note = db.query(GenomeNote).filter(GenomeNote.id == genome_note_id).first()
    if not genome_note:
        raise HTTPException(status_code=404, detail="Genome note not found")

    db.delete(genome_note)
    db.commit()
    return genome_note


@router.post("/{genome_note_id}/publish", response_model=GenomeNoteSchema)
@policy("genome_notes:write")
def publish_genome_note(
    *,
    db: Session = Depends(get_db),
    genome_note_id: UUID,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Publish a genome note.

    Returns 409 Conflict if the organism already has a published genome note.
    Use the unpublish endpoint first to unpublish the existing note.
    Only one genome note can be published per organism at a time.
    """
    try:
        genome_note = genome_note_service.publish_genome_note(db, genome_note_id)
        return genome_note
    except ValueError as e:
        error_msg = str(e)
        # Check if error is about existing published note
        if "already has a published genome note" in error_msg:
            raise HTTPException(status_code=409, detail=error_msg)
        # Otherwise it's a not found error
        raise HTTPException(status_code=404, detail=error_msg)


@router.post("/{genome_note_id}/unpublish", response_model=GenomeNoteSchema)
@policy("genome_notes:write")
def unpublish_genome_note(
    *,
    db: Session = Depends(get_db),
    genome_note_id: UUID,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Unpublish a genome note.

    Sets the genome note back to draft status.
    """
    try:
        genome_note = genome_note_service.unpublish_genome_note(db, genome_note_id)
        return genome_note
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/organism/{organism_key}/versions", response_model=List[GenomeNoteSchema])
def get_genome_note_versions(
    *,
    db: Session = Depends(get_db),
    organism_key: str,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get all versions of genome notes for a specific organism.

    Returns all genome note versions ordered by version number (descending).
    """
    genome_notes = genome_note_service.get_versions_by_organism(db, organism_key)
    return genome_notes


@router.get("/organism/{organism_key}/published", response_model=GenomeNoteSchema)
def get_published_genome_note(
    *,
    db: Session = Depends(get_db),
    organism_key: str,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get the published genome note for a specific organism.

    Returns 404 if no published genome note exists for the organism.
    """
    genome_note = genome_note_service.get_published_by_organism(db, organism_key)
    if not genome_note:
        raise HTTPException(
            status_code=404, detail=f"No published genome note found for organism {organism_key}"
        )
    return genome_note

from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import (
    get_current_active_user,
    get_current_superuser,
    get_db,
    require_role,
)
from app.models.genome_note import GenomeNote, GenomeNoteAssembly
from app.models.user import User
from app.schemas.genome_note import (
    GenomeNote as GenomeNoteSchema,
)
from app.schemas.genome_note import (
    GenomeNoteAssembly as GenomeNoteAssemblySchema,
)
from app.schemas.genome_note import (
    GenomeNoteAssemblyCreate,
    GenomeNoteAssemblyUpdate,
    GenomeNoteCreate,
    GenomeNoteUpdate,
)

router = APIRouter()


@router.get("/", response_model=List[GenomeNoteSchema])
def read_genome_notes(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    organism_key: Optional[UUID] = Query(None, description="Filter by organism key"),
    is_published: Optional[bool] = Query(None, description="Filter by publication status"),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Retrieve genome notes.
    """
    # All users can read genome notes
    query = db.query(GenomeNote)
    if organism_key:
        query = query.filter(GenomeNote.organism_key == organism_key)
    if is_published is not None:
        query = query.filter(GenomeNote.is_published == is_published)

    genome_notes = query.offset(skip).limit(limit).all()
    return genome_notes


@router.post("/", response_model=GenomeNoteSchema)
def create_genome_note(
    *,
    db: Session = Depends(get_db),
    genome_note_in: GenomeNoteCreate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Create new genome note.
    """
    # Only users with 'curator' or 'admin' role can create genome notes
    require_role(current_user, ["curator", "admin"])

    genome_note = GenomeNote(
        organism_key=genome_note_in.organism_key,
        note=genome_note_in.note,
        other_fields=genome_note_in.other_fields,
        version_chain_id=genome_note_in.version_chain_id,
        is_published=genome_note_in.is_published,
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
    # All users can read genome note details
    genome_note = db.query(GenomeNote).filter(GenomeNote.id == genome_note_id).first()
    if not genome_note:
        raise HTTPException(status_code=404, detail="Genome note not found")
    return genome_note


@router.put("/{genome_note_id}", response_model=GenomeNoteSchema)
def update_genome_note(
    *,
    db: Session = Depends(get_db),
    genome_note_id: UUID,
    genome_note_in: GenomeNoteUpdate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Update a genome note.
    """
    # Only users with 'curator' or 'admin' role can update genome notes
    require_role(current_user, ["curator", "admin"])

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
def delete_genome_note(
    *,
    db: Session = Depends(get_db),
    genome_note_id: UUID,
    current_user: User = Depends(get_current_superuser),
) -> Any:
    """
    Delete a genome note.
    """
    # Only superusers can delete genome notes
    genome_note = db.query(GenomeNote).filter(GenomeNote.id == genome_note_id).first()
    if not genome_note:
        raise HTTPException(status_code=404, detail="Genome note not found")

    db.delete(genome_note)
    db.commit()
    return genome_note


# Genome Note Assembly endpoints
@router.get("/assemblies/", response_model=List[GenomeNoteAssemblySchema])
def read_genome_note_assemblies(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    genome_note_id: Optional[UUID] = Query(None, description="Filter by genome note ID"),
    assembly_id: Optional[UUID] = Query(None, description="Filter by assembly ID"),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Retrieve genome note-assembly relationships.
    """
    # All users can read genome note-assembly relationships
    query = db.query(GenomeNoteAssembly)
    if genome_note_id:
        query = query.filter(GenomeNoteAssembly.genome_note_id == genome_note_id)
    if assembly_id:
        query = query.filter(GenomeNoteAssembly.assembly_id == assembly_id)

    relationships = query.offset(skip).limit(limit).all()
    return relationships


@router.post("/assemblies/", response_model=GenomeNoteAssemblySchema)
def create_genome_note_assembly(
    *,
    db: Session = Depends(get_db),
    relationship_in: GenomeNoteAssemblyCreate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Create new genome note-assembly relationship.
    """
    # Only users with 'curator' or 'admin' role can create genome note-assembly relationships
    require_role(current_user, ["curator", "admin"])

    relationship = GenomeNoteAssembly(
        genome_note_id=relationship_in.genome_note_id,
        assembly_id=relationship_in.assembly_id,
    )
    db.add(relationship)
    db.commit()
    db.refresh(relationship)
    return relationship


@router.put("/assemblies/{relationship_id}", response_model=GenomeNoteAssemblySchema)
def update_genome_note_assembly(
    *,
    db: Session = Depends(get_db),
    relationship_id: UUID,
    relationship_in: GenomeNoteAssemblyUpdate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Update a genome note-assembly relationship.
    """
    # Only users with 'curator' or 'admin' role can update genome note-assembly relationships
    require_role(current_user, ["curator", "admin"])

    relationship = (
        db.query(GenomeNoteAssembly).filter(GenomeNoteAssembly.id == relationship_id).first()
    )
    if not relationship:
        raise HTTPException(status_code=404, detail="Genome note-assembly relationship not found")

    update_data = relationship_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(relationship, field, value)

    db.add(relationship)
    db.commit()
    db.refresh(relationship)
    return relationship


@router.delete("/assemblies/{relationship_id}", response_model=GenomeNoteAssemblySchema)
def delete_genome_note_assembly(
    *,
    db: Session = Depends(get_db),
    relationship_id: UUID,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Delete a genome note-assembly relationship.
    """
    # Only users with 'curator' or 'admin' role can delete genome note-assembly relationships
    require_role(current_user, ["curator", "admin"])

    relationship = (
        db.query(GenomeNoteAssembly).filter(GenomeNoteAssembly.id == relationship_id).first()
    )
    if not relationship:
        raise HTTPException(status_code=404, detail="Genome note-assembly relationship not found")

    db.delete(relationship)
    db.commit()
    return relationship

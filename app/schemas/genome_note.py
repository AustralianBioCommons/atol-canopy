from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


# Base GenomeNote schema
class GenomeNoteBase(BaseModel):
    """Base GenomeNote schema with common attributes."""

    organism_key: str
    assembly_id: UUID
    title: str
    note_url: str
    is_published: bool = False


# Schema for creating a new GenomeNote
class GenomeNoteCreate(BaseModel):
    """
    Schema for creating a new GenomeNote.

    Version is auto-calculated and should not be provided.
    is_published defaults to False for new notes.
    """

    organism_key: str
    assembly_id: UUID
    title: str
    note_url: str


# Schema for updating an existing GenomeNote
class GenomeNoteUpdate(BaseModel):
    """Schema for updating an existing GenomeNote."""

    title: Optional[str] = None
    note_url: Optional[str] = None


# Schema for GenomeNote in DB
class GenomeNoteInDBBase(GenomeNoteBase):
    """Base schema for GenomeNote in DB, includes id, version, and timestamps."""

    id: UUID
    version: int
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Schema for returning GenomeNote information
class GenomeNote(GenomeNoteInDBBase):
    """Schema for returning GenomeNote information."""

    pass

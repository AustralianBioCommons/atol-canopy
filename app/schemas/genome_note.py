from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


# Base GenomeNote schema
class GenomeNoteBase(BaseModel):
    """Base GenomeNote schema with common attributes."""

    organism_key: str
    note: Optional[str] = None
    other_fields: Optional[str] = None
    version_chain_id: Optional[UUID] = None
    is_published: bool = False


# Schema for creating a new GenomeNote
class GenomeNoteCreate(GenomeNoteBase):
    """Schema for creating a new GenomeNote."""

    pass


# Schema for updating an existing GenomeNote
class GenomeNoteUpdate(BaseModel):
    """Schema for updating an existing GenomeNote."""

    organism_key: Optional[str] = None
    note: Optional[str] = None
    other_fields: Optional[str] = None
    version_chain_id: Optional[UUID] = None
    is_published: Optional[bool] = None


# Schema for GenomeNote in DB
class GenomeNoteInDBBase(GenomeNoteBase):
    """Base schema for GenomeNote in DB, includes id and timestamps."""

    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Schema for returning GenomeNote information
class GenomeNote(GenomeNoteInDBBase):
    """Schema for returning GenomeNote information."""

    pass


# Base GenomeNoteAssembly schema
class GenomeNoteAssemblyBase(BaseModel):
    """Base GenomeNoteAssembly schema with common attributes."""

    genome_note_id: UUID
    assembly_id: UUID


# Schema for creating a new GenomeNoteAssembly
class GenomeNoteAssemblyCreate(GenomeNoteAssemblyBase):
    """Schema for creating a new GenomeNoteAssembly."""

    pass


# Schema for updating an existing GenomeNoteAssembly
class GenomeNoteAssemblyUpdate(BaseModel):
    """Schema for updating an existing GenomeNoteAssembly."""

    pass


# Schema for GenomeNoteAssembly in DB
class GenomeNoteAssemblyInDBBase(GenomeNoteAssemblyBase):
    """Base schema for GenomeNoteAssembly in DB, includes id and timestamps."""

    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Schema for returning GenomeNoteAssembly information
class GenomeNoteAssembly(GenomeNoteAssemblyInDBBase):
    """Schema for returning GenomeNoteAssembly information."""

    pass

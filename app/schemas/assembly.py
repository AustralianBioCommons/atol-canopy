from datetime import datetime
from enum import Enum
from typing import Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import SubmissionStatus


# Base Assembly schema
class AssemblyBase(BaseModel):
    """Base Assembly schema with common attributes."""

    organism_key: str
    sample_id: UUID
    project_id: Optional[UUID] = None
    assembly_name: Optional[str] = None
    assembly_type: Optional[str] = None
    coverage: Optional[float] = None
    program: Optional[str] = None
    mingaplength: Optional[int] = None
    moleculetype: Optional[str] = None
    fasta: Optional[str] = None
    version: Optional[int] = None


# Schema for creating a new assembly
class AssemblyCreate(AssemblyBase):
    """Schema for creating a new assembly."""

    pass


# Schema for updating an existing assembly
class AssemblyUpdate(BaseModel):
    """Schema for updating an existing assembly."""

    organism_key: Optional[str] = None
    sample_id: Optional[UUID] = None
    project_id: Optional[UUID] = None
    assembly_name: Optional[str] = None
    assembly_type: Optional[str] = None
    coverage: Optional[float] = None
    program: Optional[str] = None
    mingaplength: Optional[int] = None
    moleculetype: Optional[str] = None
    fasta: Optional[str] = None
    version: Optional[int] = None


# Schema for assembly in DB
class AssemblyInDBBase(AssemblyBase):
    """Base schema for Assembly in DB, includes id and timestamps."""

    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Schema for returning assembly information
class Assembly(AssemblyInDBBase):
    """Schema for returning assembly information."""

    pass


# Base AssemblySubmission schema
class AssemblySubmissionBase(BaseModel):
    """Base AssemblySubmission schema with common attributes."""

    assembly_id: Optional[UUID] = None
    assembly_name: str
    authority: str = Field(default="ENA", description="Authority for the submission")
    accession: Optional[str] = None
    organism_key: str
    sample_id: UUID
    status: SubmissionStatus = Field(
        default=SubmissionStatus.DRAFT, description="Status of the submission"
    )


# Schema for creating a new assembly submission
class AssemblySubmissionCreate(AssemblySubmissionBase):
    """Schema for creating a new assembly submission."""

    internal_json: Optional[Dict] = None
    prepared_payload: Optional[Dict] = None
    response_payload: Optional[Dict] = None
    submitted_at: Optional[datetime] = None


# Schema for updating an existing assembly submission
class AssemblySubmissionUpdate(BaseModel):
    """Schema for updating an existing assembly submission."""

    assembly_id: Optional[UUID] = None
    assembly_name: Optional[str] = None
    authority: Optional[str] = None
    accession: Optional[str] = None
    organism_key: Optional[str] = None
    sample_id: Optional[UUID] = None
    internal_json: Optional[Dict] = None
    prepared_payload: Optional[Dict] = None
    response_payload: Optional[Dict] = None
    status: Optional[SubmissionStatus] = None
    submitted_at: Optional[datetime] = None


# Schema for assembly submission in DB
class AssemblySubmissionInDBBase(AssemblySubmissionBase):
    """Base schema for AssemblySubmission in DB, includes id and timestamps."""

    id: UUID
    internal_json: Optional[Dict] = None
    prepared_payload: Optional[Dict] = None
    response_payload: Optional[Dict] = None
    submitted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Schema for returning assembly submission information
class AssemblySubmission(AssemblySubmissionInDBBase):
    """Schema for returning assembly submission information."""

    pass


# AssemblyFetched schemas removed as they are no longer in the schema.sql

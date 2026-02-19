from datetime import datetime
from enum import Enum
from typing import Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import SubmissionStatus


class AssemblyFileType(str, Enum):
    """Enum for assembly file types."""
    FASTA = "FASTA"
    QC_REPORT = "QC_REPORT"
    STATISTICS = "STATISTICS"
    OTHER = "OTHER"


# Base Assembly schema
class AssemblyBase(BaseModel):
    """Base Assembly schema with common attributes."""

    organism_key: str
    sample_id: UUID
    project_id: Optional[UUID] = None
    assembly_name: str
    assembly_type: str = "clone or isolate"
    coverage: float
    program: str
    mingaplength: Optional[float] = None
    moleculetype: str = "genomic DNA"
    description: Optional[str] = None


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
    mingaplength: Optional[float] = None
    moleculetype: Optional[str] = None
    version_number: Optional[int] = None
    description: Optional[str] = None


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

    assembly_id: UUID
    authority: str = Field(default="ENA", description="Authority for the submission")
    status: SubmissionStatus = Field(
        default=SubmissionStatus.DRAFT, description="Status of the submission"
    )
    accession: Optional[str] = None
    sample_accession: Optional[str] = None
    project_accession: Optional[str] = None


# Schema for creating a new assembly submission
class AssemblySubmissionCreate(AssemblySubmissionBase):
    """Schema for creating a new assembly submission."""

    manifest_json: Optional[Dict] = None
    submission_xml: Optional[str] = None
    response_payload: Optional[Dict] = None
    submitted_at: Optional[datetime] = None
    submitted_by: Optional[UUID] = None


# Schema for updating an existing assembly submission
class AssemblySubmissionUpdate(BaseModel):
    """Schema for updating an existing assembly submission."""

    assembly_id: Optional[UUID] = None
    authority: Optional[str] = None
    status: Optional[SubmissionStatus] = None
    accession: Optional[str] = None
    sample_accession: Optional[str] = None
    project_accession: Optional[str] = None
    manifest_json: Optional[Dict] = None
    submission_xml: Optional[str] = None
    response_payload: Optional[Dict] = None
    submitted_at: Optional[datetime] = None
    submitted_by: Optional[UUID] = None


# Schema for assembly submission in DB
class AssemblySubmissionInDBBase(AssemblySubmissionBase):
    """Base schema for AssemblySubmission in DB, includes id and timestamps."""

    id: UUID
    manifest_json: Optional[Dict] = None
    submission_xml: Optional[str] = None
    response_payload: Optional[Dict] = None
    submitted_at: Optional[datetime] = None
    submitted_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Schema for returning assembly submission information
class AssemblySubmission(AssemblySubmissionInDBBase):
    """Schema for returning assembly submission information."""

    pass


# ==========================================
# AssemblyFile schemas
# ==========================================

# Base AssemblyFile schema
class AssemblyFileBase(BaseModel):
    """Base AssemblyFile schema with common attributes."""

    assembly_id: UUID
    file_type: AssemblyFileType
    file_name: str
    file_location: str
    file_size: Optional[int] = None
    file_checksum: Optional[str] = None
    file_checksum_method: str = "MD5"
    file_format: Optional[str] = None
    description: Optional[str] = None


# Schema for creating a new assembly file
class AssemblyFileCreate(AssemblyFileBase):
    """Schema for creating a new assembly file."""
    pass


# Schema for updating an existing assembly file
class AssemblyFileUpdate(BaseModel):
    """Schema for updating an existing assembly file."""

    assembly_id: Optional[UUID] = None
    file_type: Optional[AssemblyFileType] = None
    file_name: Optional[str] = None
    file_location: Optional[str] = None
    file_size: Optional[int] = None
    file_checksum: Optional[str] = None
    file_checksum_method: Optional[str] = None
    file_format: Optional[str] = None
    description: Optional[str] = None


# Schema for assembly file in DB
class AssemblyFileInDBBase(AssemblyFileBase):
    """Base schema for AssemblyFile in DB, includes id and timestamps."""

    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Schema for returning assembly file information
class AssemblyFile(AssemblyFileInDBBase):
    """Schema for returning assembly file information."""
    pass

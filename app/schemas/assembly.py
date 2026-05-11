from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import SubmissionStatus
from app.schemas.qc_read import QcReadOut


class AssemblyDataTypes(str, Enum):
    """Enum for assembly data types (sequencing platforms)."""

    PACBIO_SMRT = "PACBIO_SMRT"
    PACBIO_SMRT_HIC = "PACBIO_SMRT_HIC"
    OXFORD_NANOPORE = "OXFORD_NANOPORE"
    OXFORD_NANOPORE_HIC = "OXFORD_NANOPORE_HIC"
    PACBIO_SMRT_OXFORD_NANOPORE = "PACBIO_SMRT_OXFORD_NANOPORE"
    PACBIO_SMRT_OXFORD_NANOPORE_HIC = "PACBIO_SMRT_OXFORD_NANOPORE_HIC"


class AssemblySpecimenSampleDataType(str, Enum):
    """Atomic data types exposed by specimen-sample discovery."""

    PACBIO_SMRT = "PACBIO_SMRT"
    OXFORD_NANOPORE = "OXFORD_NANOPORE"
    HIC = "Hi-C"
    RNASEQ = "RNA-Seq"


class AssemblyFileType(str, Enum):
    """Enum for assembly file types."""

    FASTA = "FASTA"
    QC_REPORT = "QC_REPORT"
    STATISTICS = "STATISTICS"
    OTHER = "OTHER"


# Base Assembly schema
class AssemblyBase(BaseModel):
    """Base Assembly schema with common attributes."""

    taxon_id: int
    sample_id: UUID
    project_id: Optional[UUID] = None
    assembly_name: Optional[str] = None
    assembly_type: str = "clone or isolate"
    tol_id: Optional[str] = None
    data_types: AssemblyDataTypes
    coverage: Optional[float] = None
    program: Optional[str] = None
    mingaplength: Optional[float] = None
    moleculetype: str = "genomic DNA"
    description: Optional[str] = None
    version: int = 1
    status: str = "requested"


# Schema for creating a new assembly
class AssemblyCreate(AssemblyBase):
    """Schema for creating a new assembly."""

    pass


# Schema for creating assembly from experiments (taxon_id derived from route parameter)
class AssemblyCreateFromExperiments(BaseModel):
    """Schema for creating assembly from experiments - taxon_id is auto-filled from the path."""

    sample_id: UUID
    project_id: Optional[UUID] = None
    assembly_name: str
    assembly_type: str = "clone or isolate"
    tol_id: str
    data_types: Optional[AssemblyDataTypes] = None  # Auto-detected, can be overridden
    coverage: float
    program: str
    mingaplength: Optional[float] = None
    moleculetype: str = "genomic DNA"
    description: Optional[str] = None


class AssemblyIntent(BaseModel):
    """Schema for reserving an assembly version and generating a manifest."""

    tol_id: Optional[str] = None
    long_read_specimen_sample_id: UUID
    hic_specimen_sample_id: Optional[UUID] = None


class AssemblyIntentResponse(BaseModel):
    """Response envelope for assembly intent creation."""

    assembly_id: UUID
    version: int
    status: str
    manifest_json: Dict[str, Any]


class AssemblySpecimenSampleOption(BaseModel):
    """Assembly discovery metadata for a specimen sample."""

    sample_id: UUID
    specimen_id: Optional[str] = None
    sex: Optional[str] = None
    available_data_types: List[AssemblySpecimenSampleDataType] = Field(default_factory=list)
    qc_reads: List[QcReadOut] = Field(default_factory=list)


class AssemblySpecimenSampleDiscoveryResponse(BaseModel):
    """Response schema for assembly specimen-sample discovery."""

    taxon_id: int
    specimen_samples: List[AssemblySpecimenSampleOption]


class AssemblyIntentCancel(BaseModel):
    """Schema for cancelling an existing assembly intent."""

    assembly_id: UUID
    version: Optional[int] = None


# Schema for updating an existing assembly
class AssemblyUpdate(BaseModel):
    """Schema for updating an existing assembly."""

    taxon_id: Optional[int] = None
    sample_id: Optional[UUID] = None
    project_id: Optional[UUID] = None
    assembly_name: Optional[str] = None
    assembly_type: Optional[str] = None
    tol_id: Optional[str] = None
    coverage: Optional[float] = None
    program: Optional[str] = None
    mingaplength: Optional[float] = None
    moleculetype: Optional[str] = None
    version_number: Optional[int] = None
    description: Optional[str] = None
    status: Optional[str] = None


# Schema for assembly in DB
class AssemblyInDBBase(AssemblyBase):
    """Base schema for Assembly in DB, includes id and timestamps."""

    id: UUID
    long_read_specimen_sample_id: Optional[UUID] = None
    hic_specimen_sample_id: Optional[UUID] = None
    manifest_json: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


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
    response_payload: Optional[Dict] = None
    submitted_at: Optional[datetime] = None
    submitted_by: Optional[UUID] = None


# Schema for assembly submission in DB
class AssemblySubmissionInDBBase(AssemblySubmissionBase):
    """Base schema for AssemblySubmission in DB, includes id and timestamps."""

    id: UUID
    manifest_json: Optional[Dict] = None
    response_payload: Optional[Dict] = None
    submitted_at: Optional[datetime] = None
    submitted_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


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


# ==========================================
# AssemblyStageRun schemas
# ==========================================


class AssemblyStageRunFileCreate(BaseModel):
    """File payload for a stage run."""

    storage_type: str
    storage_uri: str
    storage_details: Dict[str, Any] = {}
    sha256sum: str


class AssemblyStageRunCreate(BaseModel):
    """Schema for reporting a stage run result."""

    stage_name: str
    status: str
    external_run_id: Optional[str] = None
    attempt: int = 1
    stats: Dict[str, Any] = {}
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    files: List[AssemblyStageRunFileCreate] = []


class AssemblyStageRunUpdate(BaseModel):
    """Schema for updating an existing stage run. If files is provided, replaces all existing files."""

    status: Optional[str] = None
    external_run_id: Optional[str] = None
    stats: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    files: Optional[List[AssemblyStageRunFileCreate]] = None


class AssemblyStageRunFileOut(BaseModel):
    """Stage run file response schema."""

    id: UUID
    assembly_stage_run_id: UUID
    storage_type: str
    storage_uri: str
    storage_details: Dict[str, Any]
    sha256sum: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AssemblyStageRunOut(BaseModel):
    """Stage run response schema."""

    id: UUID
    assembly_id: UUID
    stage_name: str
    status: str
    external_run_id: Optional[str]
    attempt: int
    stats: Dict[str, Any]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    files: List[AssemblyStageRunFileOut] = []

    model_config = ConfigDict(from_attributes=True)

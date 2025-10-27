from datetime import datetime
from enum import Enum
from typing import Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field

# Enum for submission status
from app.schemas.common import SubmissionStatus

# Base Experiment schema
class ExperimentBase(BaseModel):
    """Base Experiment schema with common attributes."""
    sample_id: UUID
    # BPA fields
    bpa_package_id: str
    bpa_json: Optional[Dict] = None


# Schema for creating a new experiment
class ExperimentCreate(ExperimentBase):
    """Schema for creating a new experiment."""
    design_description: Optional[str] = None
    bpa_package_id: Optional[str] = None
    bpa_library_id: Optional[str] = None
    library_strategy: Optional[str] = None
    library_source: Optional[str] = None
    insert_size: Optional[int] = None
    library_construction_protocol: Optional[str] = None
    library_selection: Optional[str] = None
    library_layout: Optional[str] = None
    instrument_model: Optional[str] = None
    platform: Optional[str] = None
    material_extracted_by: Optional[str] = None
    material_extraction_date: Optional[str] = None
    library_prepared_by: Optional[str] = None
    library_prepared_date: Optional[str] = None
    sequencing_kit: Optional[str] = None
    flowcell_type: Optional[str] = None
    base_caller_model: Optional[str] = None
    data_owner: Optional[str] = None
    extraction_method: Optional[str] = None
    nucleic_acid_treatment: Optional[str] = None
    extraction_protocol_DOI: Optional[str] = None
    nucleic_acid_conc: Optional[str] = None
    nucleic_acid_volume: Optional[str] = None
    GAL: Optional[str] = None
    sample_access_date: Optional[str] = None

# Schema for updating an existing experiment
class ExperimentUpdate(ExperimentBase):
    """Schema for updating an existing experiment."""
    design_description: Optional[str] = None
    bpa_package_id: Optional[str] = None
    bpa_library_id: Optional[str] = None
    library_strategy: Optional[str] = None
    library_source: Optional[str] = None
    insert_size: Optional[int] = None
    library_construction_protocol: Optional[str] = None
    library_selection: Optional[str] = None
    library_layout: Optional[str] = None
    instrument_model: Optional[str] = None
    platform: Optional[str] = None
    material_extracted_by: Optional[str] = None
    material_extraction_date: Optional[str] = None
    library_prepared_by: Optional[str] = None
    library_prepared_date: Optional[str] = None
    sequencing_kit: Optional[str] = None
    flowcell_type: Optional[str] = None
    base_caller_model: Optional[str] = None
    data_owner: Optional[str] = None
    extraction_method: Optional[str] = None
    nucleic_acid_treatment: Optional[str] = None
    extraction_protocol_DOI: Optional[str] = None
    nucleic_acid_conc: Optional[str] = None
    nucleic_acid_volume: Optional[str] = None
    GAL: Optional[str] = None
    sample_access_date: Optional[str] = None


# Schema for experiment in DB
class ExperimentInDBBase(ExperimentBase):
    """Base schema for Experiment in DB, includes id and timestamps."""
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Schema for returning experiment information
class Experiment(ExperimentInDBBase):
    """Schema for returning experiment information."""
    pass


# Base ExperimentSubmission schema
class ExperimentSubmissionBase(BaseModel):
    """Base ExperimentSubmission schema with common attributes."""
    sample_id: UUID
    project_id: Optional[UUID] = None
    authority: str = Field(default="ENA", description="Authority for the submission")
    status: SubmissionStatus = Field(default=SubmissionStatus.DRAFT, description="Status of the submission")
    entity_type_const: str = Field(default="experiment", description="Entity type constant for foreign key constraints")


# Schema for creating a new experiment submission
class ExperimentSubmissionCreate(ExperimentSubmissionBase):
    """Schema for creating a new experiment submission."""
    experiment_id: Optional[UUID] = None
    project_accession: Optional[str] = None
    sample_accession: Optional[str] = None
    prepared_payload: Optional[Dict] = None
    response_payload: Optional[Dict] = None
    accession: Optional[str] = None
    submitted_at: Optional[datetime] = None


# Schema for updating an existing experiment submission
class ExperimentSubmissionUpdate(BaseModel):
    """Schema for updating an existing experiment submission."""
    sample_id: Optional[UUID] = None
    project_id: Optional[UUID] = None
    authority: Optional[str] = None
    project_accession: Optional[str] = None
    sample_accession: Optional[str] = None
    prepared_payload: Optional[Dict] = None
    response_payload: Optional[Dict] = None
    status: Optional[SubmissionStatus] = None
    accession: Optional[str] = None
    submitted_at: Optional[datetime] = None


# Schema for experiment submission in DB
class ExperimentSubmissionInDBBase(ExperimentSubmissionBase):
    """Base schema for ExperimentSubmission in DB, includes id and timestamps."""
    id: UUID
    experiment_id: Optional[UUID] = None
    project_accession: Optional[str] = None
    sample_accession: Optional[str] = None
    prepared_payload: Optional[Dict] = None
    response_payload: Optional[Dict] = None
    accession: Optional[str] = None
    submitted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Schema for returning experiment submission information
class ExperimentSubmission(ExperimentSubmissionInDBBase):
    """Schema for returning experiment submission information."""
    pass


# ExperimentFetched schemas removed as they are no longer in the schema.sql

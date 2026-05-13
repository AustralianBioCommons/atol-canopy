from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# Enum for submission status
from app.schemas.common import SubmissionStatus


class ExperimentBase(BaseModel):
    sample_id: UUID
    bpa_package_id: str
    bioplatforms_base_url: Optional[str] = None
    design_description: Optional[str] = None
    bpa_library_id: Optional[str] = None
    library_strategy: Optional[str] = None
    library_source: Optional[str] = None
    insert_size: Optional[str] = None
    library_construction_protocol: Optional[str] = None
    library_selection: Optional[str] = None
    library_layout: Optional[str] = None
    instrument_model: Optional[str] = None
    platform: Optional[str] = None
    material_extracted_by: Optional[str] = None
    library_prepared_by: Optional[str] = None
    sequencing_kit: Optional[str] = None
    flowcell_type: Optional[str] = None
    base_caller_model: Optional[str] = None
    data_owner: Optional[str] = None
    project_collaborators: Optional[str] = None
    extraction_method: Optional[str] = None
    nucleic_acid_treatment: Optional[str] = None
    extraction_protocol_doi: Optional[str] = None
    nucleic_acid_conc: Optional[str] = None
    nucleic_acid_volume: Optional[str] = None
    gal: Optional[str] = None
    raw_data_release_date: Optional[str] = None


class ExperimentPayloadExtras(BaseModel):
    """Legacy payload-only fields preserved for ENA payload generation."""

    material_extraction_date: Optional[str] = None
    library_prepared_date: Optional[str] = None
    sample_access_date: Optional[str] = None


class ExperimentCreate(ExperimentBase, ExperimentPayloadExtras):
    """Schema for creating a new experiment."""


class ExperimentUpdate(ExperimentPayloadExtras):
    """Schema for updating an existing experiment."""

    sample_id: Optional[UUID] = None
    bpa_package_id: Optional[str] = None
    bioplatforms_base_url: Optional[str] = None
    design_description: Optional[str] = None
    bpa_library_id: Optional[str] = None
    library_strategy: Optional[str] = None
    library_source: Optional[str] = None
    insert_size: Optional[str] = None
    library_construction_protocol: Optional[str] = None
    library_selection: Optional[str] = None
    library_layout: Optional[str] = None
    instrument_model: Optional[str] = None
    platform: Optional[str] = None
    material_extracted_by: Optional[str] = None
    library_prepared_by: Optional[str] = None
    sequencing_kit: Optional[str] = None
    flowcell_type: Optional[str] = None
    base_caller_model: Optional[str] = None
    data_owner: Optional[str] = None
    project_collaborators: Optional[str] = None
    extraction_method: Optional[str] = None
    nucleic_acid_treatment: Optional[str] = None
    extraction_protocol_doi: Optional[str] = None
    nucleic_acid_conc: Optional[str] = None
    nucleic_acid_volume: Optional[str] = None
    gal: Optional[str] = None
    raw_data_release_date: Optional[str] = None


class ExperimentInDBBase(ExperimentBase):
    id: UUID
    project_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Experiment(ExperimentInDBBase):
    pass


class ExperimentDetail(ExperimentInDBBase):
    """Detailed experiment schema used by nested aggregate endpoints."""

    project_id: UUID
    bioplatforms_base_url: Optional[str] = None
    design_description: Optional[str] = None
    bpa_library_id: Optional[str] = None
    library_strategy: Optional[str] = None
    library_source: Optional[str] = None
    insert_size: Optional[str] = None
    library_construction_protocol: Optional[str] = None
    library_selection: Optional[str] = None
    library_layout: Optional[str] = None
    instrument_model: Optional[str] = None
    platform: Optional[str] = None
    material_extracted_by: Optional[str] = None
    library_prepared_by: Optional[str] = None
    sequencing_kit: Optional[str] = None
    flowcell_type: Optional[str] = None
    base_caller_model: Optional[str] = None
    data_owner: Optional[str] = None
    project_collaborators: Optional[str] = None
    extraction_method: Optional[str] = None
    nucleic_acid_treatment: Optional[str] = None
    extraction_protocol_doi: Optional[str] = None
    nucleic_acid_conc: Optional[str] = None
    nucleic_acid_volume: Optional[str] = None
    gal: Optional[str] = None
    raw_data_release_date: Optional[str] = None


# Base ExperimentSubmission schema
class ExperimentSubmissionBase(BaseModel):
    authority: str = Field(default="ENA", description="Authority for the submission")
    status: SubmissionStatus = Field(
        default=SubmissionStatus.DRAFT, description="Status of the submission"
    )
    entity_type_const: str = Field(
        default="experiment", description="Entity type constant for foreign key constraints"
    )


# Schema for creating a new experiment submission
class ExperimentSubmissionCreate(ExperimentSubmissionBase):
    experiment_id: Optional[UUID] = None
    prepared_payload: Optional[Dict[str, Any]] = None
    response_payload: Optional[Dict[str, Any]] = None
    accession: Optional[str] = None
    submitted_at: Optional[datetime] = None


class ExperimentSubmissionUpdate(BaseModel):
    authority: Optional[str] = None
    prepared_payload: Optional[Dict[str, Any]] = None
    response_payload: Optional[Dict[str, Any]] = None
    status: Optional[SubmissionStatus] = None
    accession: Optional[str] = None
    submitted_at: Optional[datetime] = None


class ExperimentSubmissionInDBBase(ExperimentSubmissionBase):
    id: UUID
    experiment_id: Optional[UUID] = None
    prepared_payload: Optional[Dict[str, Any]] = None
    response_payload: Optional[Dict[str, Any]] = None
    accession: Optional[str] = None
    submitted_at: Optional[datetime] = None
    attempt_id: Optional[UUID] = None
    finalised_attempt_id: Optional[UUID] = None
    lock_acquired_at: Optional[datetime] = None
    lock_expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExperimentSubmission(ExperimentSubmissionInDBBase):
    pass


# ExperimentFetched schemas removed as they are no longer in the schema.sql

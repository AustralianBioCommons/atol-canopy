from datetime import datetime
from enum import Enum
from typing import Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# Enum for submission status
from app.schemas.common import SampleKind, SubmissionStatus


# Base Sample schema (aligns with schema.sql columns except id/timestamps/bpa_json)
class SampleBase(BaseModel):
    """Base Sample schema aligned to DB columns (excluding id, timestamps, bpa_json)."""

    organism_key: Optional[str] = None
    bpa_sample_id: Optional[str] = None
    specimen_id: Optional[str] = None
    specimen_id_description: Optional[str] = None
    identified_by: Optional[str] = None
    specimen_custodian: Optional[str] = None
    sample_custodian: Optional[str] = None
    lifestage: Optional[str] = None
    sex: Optional[str] = None
    organism_part: Optional[str] = None
    region_and_locality: Optional[str] = None
    state_or_region: Optional[str] = None
    country_or_sea: Optional[str] = None
    indigenous_location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    elevation: Optional[float] = None
    depth: Optional[float] = None
    habitat: Optional[str] = None
    collection_method: Optional[str] = None
    collection_date: Optional[str] = None
    collected_by: Optional[str] = None
    collecting_institution: Optional[str] = None
    collection_permit: Optional[str] = None
    data_context: Optional[str] = None
    bioplatforms_project_id: Optional[str] = None
    title: Optional[str] = None
    sample_same_as: Optional[str] = None
    sample_derived_from: Optional[str] = None
    specimen_voucher: Optional[str] = None
    tolid: Optional[str] = None
    preservation_method: Optional[str] = None
    preservation_temperature: Optional[str] = None
    project_name: Optional[str] = None
    biosample_accession: Optional[str] = None

    # Parent-child relationship fields
    derived_from_sample_id: Optional[UUID] = None
    kind: Optional[SampleKind] = None
    extensions: Optional[Dict] = None


# Schema for creating a new sample
class SampleCreate(SampleBase):
    """Schema for creating a new sample. Includes alias inputs used by importer."""

    pass


# Schema for updating an existing sample
class SampleUpdate(SampleBase):
    """Schema for updating an existing sample. Includes same alias inputs as create."""

    pass


# Schema for sample in DB
class SampleInDBBase(SampleBase):
    """Base schema for Sample in DB, includes id, timestamps and bpa_json."""

    id: UUID
    # bpa_json: Dict
    created_at: datetime
    updated_at: datetime
    
    # Override to make these required in DB responses
    kind: SampleKind

    model_config = ConfigDict(from_attributes=True)


# Schema for returning sample information
class Sample(SampleInDBBase):
    """Schema for returning sample information."""

    pass


# Base SampleSubmission schema
class SampleSubmissionBase(BaseModel):
    """Base SampleSubmission schema with common attributes."""

    authority: str = Field(default="ENA", description="Authority for the submission")
    status: SubmissionStatus = Field(
        default=SubmissionStatus.DRAFT, description="Status of the submission"
    )
    entity_type_const: str = Field(
        default="sample", description="Entity type constant for foreign key constraints"
    )


# Schema for creating a new sample submission
class SampleSubmissionCreate(SampleSubmissionBase):
    """Schema for creating a new sample submission."""

    sample_id: UUID
    prepared_payload: Optional[Dict] = None
    response_payload: Optional[Dict] = None
    accession: Optional[str] = None
    biosample_accession: Optional[str] = None
    submitted_at: Optional[datetime] = None


# Schema for updating an existing sample submission
class SampleSubmissionUpdate(BaseModel):
    """Schema for updating an existing sample submission."""

    authority: Optional[str] = None
    prepared_payload: Optional[Dict] = None
    response_payload: Optional[Dict] = None
    status: Optional[SubmissionStatus] = None
    accession: Optional[str] = None
    biosample_accession: Optional[str] = None
    submitted_at: Optional[datetime] = None


# Schema for sample submission in DB
class SampleSubmissionInDBBase(SampleSubmissionBase):
    """Base schema for SampleSubmission in DB, includes id and timestamps."""

    id: UUID
    sample_id: UUID
    prepared_payload: Optional[Dict] = None
    response_payload: Optional[Dict] = None
    accession: Optional[str] = None
    biosample_accession: Optional[str] = None
    submitted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Schema for returning sample submission information
class SampleSubmission(SampleSubmissionInDBBase):
    """Schema for returning sample submission information."""

    pass


# SampleFetched schemas removed as they are no longer in the schema.sql

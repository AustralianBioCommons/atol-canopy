from datetime import datetime
from enum import Enum
from typing import Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# Enum for submission status
from app.schemas.common import SubmissionStatus

# Base Sample schema
class SampleBase(BaseModel):
    """Base Sample schema with common attributes."""
    organism_key: Optional[str] = None
    bpa_sample_id: Optional[str] = None
    bpa_json: Optional[Dict] = None

# Schema for creating a new sample
class SampleCreate(SampleBase):
    """Schema for creating a new sample."""
    pass


# Schema for updating an existing sample
class SampleUpdate(BaseModel):
    """Schema for updating an existing sample."""
    organism_key: Optional[str] = None
    bpa_sample_id: Optional[str] = None
    bpa_json: Optional[Dict] = None

# Schema for sample in DB
class SampleInDBBase(SampleBase):
    """Base schema for Sample in DB, includes id and timestamps."""
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Schema for returning sample information
class Sample(SampleInDBBase):
    """Schema for returning sample information."""
    pass


# Base SampleSubmission schema
class SampleSubmissionBase(BaseModel):
    """Base SampleSubmission schema with common attributes."""
    authority: str = Field(default="ENA", description="Authority for the submission")
    status: SubmissionStatus = Field(default=SubmissionStatus.DRAFT, description="Status of the submission")
    entity_type_const: str = Field(default="sample", description="Entity type constant for foreign key constraints")


# Schema for creating a new sample submission
class SampleSubmissionCreate(SampleSubmissionBase):
    """Schema for creating a new sample submission."""
    sample_id: Optional[UUID] = None
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
    sample_id: Optional[UUID] = None
    prepared_payload: Optional[Dict] = None
    response_payload: Optional[Dict] = None
    accession: Optional[str] = None
    biosample_accession: Optional[str] = None
    submitted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Schema for returning sample submission information
class SampleSubmission(SampleSubmissionInDBBase):
    """Schema for returning sample submission information."""
    pass


# SampleFetched schemas removed as they are no longer in the schema.sql

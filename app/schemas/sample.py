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
    scientific_name: Optional[str] = None
    genus: Optional[str] = None
    species: Optional[str] = None
    infraspecific_epithet: Optional[str] = None
    isolate: Optional[str] = None
    family: Optional[str] = None
    order_or_group: Optional[str] = None
    class_name: Optional[str] = None
    phylum: Optional[str] = None
    authority: Optional[str] = None
    # TODO remove authority ^^
    taxon_id: Optional[str] = None
    common_name: Optional[str] = None
    voucher_id: Optional[str] = None
    voucher_institution: Optional[str] = None
    identified_by: Optional[str] = None
    identifier_institute: Optional[str] = None
    taxon_remarks: Optional[str] = None
    specimen_custodian: Optional[str] = None
    sample_custodian: Optional[str] = None
    lifestage: Optional[str] = None
    sex: Optional[str] = None
    organism_part: Optional[str] = None
    host_scientific_name: Optional[str] = None
    collection_location: Optional[str] = None
    decimal_latitude: Optional[str] = None
    decimal_longitude: Optional[str] = None
    elevation: Optional[str] = None
    depth: Optional[str] = None
    habitat: Optional[str] = None
    description_of_collection_method: Optional[str] = None
    date_of_collection: Optional[str] = None
    collected_by: Optional[str] = None
    collector_institute: Optional[str] = None
    collection_permit: Optional[str] = None
    atol_sample_id: Optional[str] = None
    sample_name: Optional[str] = None
    specimen_id: Optional[str] = None
    material_extracted_by: Optional[str] = None
    material_extraction_date: Optional[str] = None
    sample_submitter: Optional[str] = None
    sample_submission_date: Optional[str] = None
    sequencing_facility: Optional[str] = None
    data_context: Optional[str] = None
    bioplatforms_project_code: Optional[str] = None
    sample_access_date: Optional[str] = None
    bioplatforms_project: Optional[str] = None
    bioplatforms_project_id: Optional[str] = None
    bioplatforms_project_description: Optional[str] = None
    bioplatforms_project_url: Optional[str] = None


# Schema for updating an existing sample
class SampleUpdate(SampleBase):
    """Schema for updating an existing sample."""
    scientific_name: Optional[str] = None
    genus: Optional[str] = None
    species: Optional[str] = None
    infraspecific_epithet: Optional[str] = None
    isolate: Optional[str] = None
    family: Optional[str] = None
    order_or_group: Optional[str] = None
    class_name: Optional[str] = None
    phylum: Optional[str] = None
    authority: Optional[str] = None
    taxon_id: Optional[str] = None
    common_name: Optional[str] = None
    voucher_id: Optional[str] = None
    voucher_institution: Optional[str] = None
    identified_by: Optional[str] = None
    identifier_institute: Optional[str] = None
    taxon_remarks: Optional[str] = None
    specimen_custodian: Optional[str] = None
    sample_custodian: Optional[str] = None
    lifestage: Optional[str] = None
    sex: Optional[str] = None
    organism_part: Optional[str] = None
    host_scientific_name: Optional[str] = None
    collection_location: Optional[str] = None
    decimal_latitude: Optional[str] = None
    decimal_longitude: Optional[str] = None
    elevation: Optional[str] = None
    depth: Optional[str] = None
    habitat: Optional[str] = None
    description_of_collection_method: Optional[str] = None
    date_of_collection: Optional[str] = None
    collected_by: Optional[str] = None
    collector_institute: Optional[str] = None
    collection_permit: Optional[str] = None
    atol_sample_id: Optional[str] = None
    sample_name: Optional[str] = None
    specimen_id: Optional[str] = None
    material_extracted_by: Optional[str] = None
    material_extraction_date: Optional[str] = None
    sample_submitter: Optional[str] = None
    sample_submission_date: Optional[str] = None
    sequencing_facility: Optional[str] = None
    data_context: Optional[str] = None
    bioplatforms_project_code: Optional[str] = None
    sample_access_date: Optional[str] = None
    bioplatforms_project: Optional[str] = None
    bioplatforms_project_id: Optional[str] = None
    bioplatforms_project_description: Optional[str] = None
    bioplatforms_project_url: Optional[str] = None

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

    class Config:
        from_attributes = True


# Schema for returning sample submission information
class SampleSubmission(SampleSubmissionInDBBase):
    """Schema for returning sample submission information."""
    pass


# SampleFetched schemas removed as they are no longer in the schema.sql

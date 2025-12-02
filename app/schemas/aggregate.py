from datetime import datetime
from typing import Dict, Any, List, Optional
from uuid import UUID

from pydantic import BaseModel


class SampleSubmissionJson(BaseModel):
    """Schema for sample prepared_payload data with sample ID"""
    sample_id: UUID
    bpa_sample_id: Optional[str] = None
    prepared_payload: Optional[Dict[str, Any]] = None
    accession: Optional[str] = None
    authority: Optional[str] = None
    response_payload: Optional[Dict[str, Any]] = None
    submitted_at: Optional[datetime] = None
    biosample_accession: Optional[str] = None
    status: Optional[str] = None

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    attempt_id: Optional[UUID] = None
    finalised_attempt_id: Optional[UUID] = None
    lock_acquired_at: Optional[datetime] = None
    lock_expires_at: Optional[datetime] = None


class ExperimentSubmissionJson(BaseModel):
    """Schema for experiment prepared_payload data with experiment ID"""
    experiment_id: UUID
    bpa_package_id: Optional[str] = None
    prepared_payload: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    accession: Optional[str] = None
    sample_accession: Optional[str] = None
    project_accession: Optional[str] = None
    authority: Optional[str] = None
    response_payload: Optional[Dict[str, Any]] = None
    submitted_at: Optional[datetime] = None

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    attempt_id: Optional[UUID] = None
    finalised_attempt_id: Optional[UUID] = None
    lock_acquired_at: Optional[datetime] = None
    lock_expires_at: Optional[datetime] = None


class ReadSubmissionJson(BaseModel):
    """Schema for read prepared_payload data with read ID"""
    read_id: UUID
    experiment_id: UUID
    file_name: Optional[str] = None
    prepared_payload: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    accession: Optional[str] = None
    experiment_accession: Optional[str] = None
    authority: Optional[str] = None
    response_payload: Optional[Dict[str, Any]] = None
    submitted_at: Optional[datetime] = None

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    attempt_id: Optional[UUID] = None
    finalised_attempt_id: Optional[UUID] = None
    lock_acquired_at: Optional[datetime] = None
    lock_expires_at: Optional[datetime] = None


class OrganismSubmissionJsonResponse(BaseModel):
    """Schema for returning all prepared_payload data related to an organism"""
    grouping_key: str
    tax_id: int
    scientific_name: Optional[str] = None
    common_name: Optional[str] = None
    common_name_source: Optional[str] = None
    samples: List[SampleSubmissionJson] = []
    experiments: List[ExperimentSubmissionJson] = []
    reads: List[ReadSubmissionJson] = []

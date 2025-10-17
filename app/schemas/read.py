from datetime import datetime
from typing import Optional, Dict, Any, Literal
from uuid import UUID

from pydantic import BaseModel


# Base Read schema
class ReadBase(BaseModel):
    """Base Read schema with common attributes."""
    experiment_id: UUID
    bpa_resource_id: str
    bpa_json: Dict[str, Any]


# Schema for creating a new Read
class ReadCreate(ReadBase):
    """Schema for creating a new Read."""
    pass


# Schema for updating an existing Read
class ReadUpdate(BaseModel):
    """Schema for updating an existing Read."""
    experiment_id: Optional[UUID] = None
    bpa_resource_id: Optional[str] = None
    bpa_json: Optional[Dict[str, Any]] = None


# Schema for Read in DB
class ReadInDBBase(ReadBase):
    """Base schema for Read in DB, includes id and timestamps."""
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Schema for returning Read information
class Read(ReadInDBBase):
    """Schema for returning Read information."""
    pass


# Base ReadSubmission schema
class ReadSubmissionBase(BaseModel):
    """Base ReadSubmission schema with common attributes."""
    read_id: UUID
    authority: str = "ENA"
    status: Literal["draft", "ready", "submitted", "accepted", "rejected", "replaced"] = "draft"
    experiment_id: UUID
    project_id: UUID
    entity_type_const: str = "read"


# Schema for creating a new read submission
class ReadSubmissionCreate(ReadSubmissionBase):
    """Schema for creating a new read submission."""
    prepared_payload: Dict[str, Any]
    response_payload: Optional[Dict[str, Any]] = None
    experiment_accession: Optional[str] = None
    accession: Optional[str] = None
    submitted_at: Optional[datetime] = None


# Schema for updating an existing read submission
class ReadSubmissionUpdate(BaseModel):
    """Schema for updating an existing read submission."""
    read_id: Optional[UUID] = None
    authority: Optional[str] = None
    status: Optional[Literal["draft", "ready", "submitted", "accepted", "rejected", "replaced"]] = None
    experiment_id: Optional[UUID] = None
    project_id: Optional[UUID] = None
    prepared_payload: Optional[Dict[str, Any]] = None
    response_payload: Optional[Dict[str, Any]] = None
    experiment_accession: Optional[str] = None
    accession: Optional[str] = None
    submitted_at: Optional[datetime] = None


# Schema for read submission in DB
class ReadSubmissionInDBBase(ReadSubmissionBase):
    """Base schema for ReadSubmission in DB, includes id and timestamps."""
    id: UUID
    prepared_payload: Dict[str, Any]
    response_payload: Optional[Dict[str, Any]] = None
    experiment_accession: Optional[str] = None
    accession: Optional[str] = None
    submitted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Schema for returning read submission information
class ReadSubmission(ReadSubmissionInDBBase):
    """Schema for returning read submission information."""
    pass

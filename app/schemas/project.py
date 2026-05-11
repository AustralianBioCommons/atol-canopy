from datetime import datetime
from typing import Any, Dict, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

ProjectType = Literal["root", "genomic_data", "assembly"]


# Base Project schema
class ProjectBase(BaseModel):
    """Base Project schema with common attributes."""

    taxon_id: int
    project_type: ProjectType
    project_accession: Optional[str] = None
    study_type: str
    alias: str
    title: str
    description: str
    centre_name: Optional[str] = "AToL"
    study_attributes: Optional[Dict[str, Any]] = None
    submitted_at: Optional[datetime] = None
    status: str = "draft"
    authority: str = "ENA"


# Schema for creating a new Project
class ProjectCreate(ProjectBase):
    """Schema for creating a new Project."""

    pass


# Schema for updating an existing Project
class ProjectUpdate(BaseModel):
    """Schema for updating an existing Project."""

    taxon_id: Optional[int] = None
    project_type: Optional[ProjectType] = None
    project_accession: Optional[str] = None
    study_type: Optional[str] = None
    alias: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    centre_name: Optional[str] = None
    study_attributes: Optional[Dict[str, Any]] = None
    submitted_at: Optional[datetime] = None
    status: Optional[str] = None
    authority: Optional[str] = None


# Schema for Project in DB
class ProjectInDBBase(ProjectBase):
    """Base schema for Project in DB, includes id and timestamps."""

    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Schema for returning Project information
class Project(ProjectInDBBase):
    """Schema for returning Project information."""

    pass

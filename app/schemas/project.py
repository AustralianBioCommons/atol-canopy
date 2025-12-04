from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


# Base Project schema
class ProjectBase(BaseModel):
    """Base Project schema with common attributes."""
    project_accession: str
    alias: str
    alias_md5: str
    study_name: str
    new_study_type: Optional[str] = None
    study_abstract: Optional[str] = None


# Schema for creating a new Project
class ProjectCreate(ProjectBase):
    """Schema for creating a new Project."""
    pass


# Schema for updating an existing Project
class ProjectUpdate(BaseModel):
    """Schema for updating an existing Project."""
    alias: Optional[str] = None
    alias_md5: Optional[str] = None
    study_name: Optional[str] = None
    new_study_type: Optional[str] = None
    study_abstract: Optional[str] = None


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

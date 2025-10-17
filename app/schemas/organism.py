from datetime import datetime
from enum import Enum
from typing import Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# Enum for submission status
from app.schemas.common import SubmissionStatus

# Base Organism schema
class OrganismBase(BaseModel):
    """Base Organism schema with common attributes."""
    grouping_key: str
    tax_id: int
    scientific_name: str
    common_name: Optional[str] = None
    common_name_source: Optional[str] = None
    bpa_json: Optional[Dict] = None
    taxonomy_lineage_json: Optional[Dict] = None

# Schema for creating a new organism
class OrganismCreate(OrganismBase):
    """Schema for creating a new organism."""
    pass


# Schema for updating an existing organism
class OrganismUpdate(BaseModel):
    """Schema for updating an existing organism."""
    # TODO ignore pk?
    # tax_id: int = None
    scientific_name: Optional[str] = None
    common_name: Optional[str] = None
    common_name_source: Optional[str] = None
    bpa_json: Optional[Dict] = None
    taxonomy_lineage_json: Optional[Dict] = None


# Schema for organism in DB
class OrganismInDBBase(OrganismBase):
    """Base schema for Organism in DB, includes id and timestamps."""
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Schema for returning organism information
class Organism(OrganismInDBBase):
    """Schema for returning organism information."""
    pass

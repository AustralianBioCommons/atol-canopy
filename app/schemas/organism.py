from datetime import datetime
from enum import Enum
from typing import Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

# Enum for submission status
from app.schemas.common import SubmissionStatus


# Base Organism schema
class OrganismBase(BaseModel):
    """Base Organism schema with common attributes."""

    taxon_id: int
    scientific_name: Optional[str] = None
    common_name: Optional[str] = None
    common_name_source: Optional[str] = None
    genus: Optional[str] = None
    species: Optional[str] = None
    infraspecific_epithet: Optional[str] = None
    culture_or_strain_id: Optional[str] = None
    authority: Optional[str] = None
    atol_scientific_name: Optional[str] = None
    tax_string: Optional[str] = None
    ncbi_order: Optional[str] = None
    ncbi_family: Optional[str] = None
    busco_dataset_name: Optional[str] = None
    augustus_dataset_name: Optional[str] = None
    bpa_json: Optional[Dict] = None
    taxonomy_lineage_json: Optional[Dict] = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy_keys(cls, data):
        if isinstance(data, dict) and "taxon_id" not in data and "tax_id" in data:
            data = dict(data)
            data["taxon_id"] = data.pop("tax_id")
        return data


# Schema for creating a new organism
class OrganismCreate(OrganismBase):
    """Schema for creating a new organism."""

    pass


# Schema for updating an existing organism
class OrganismUpdate(BaseModel):
    """Schema for updating an existing organism."""

    scientific_name: Optional[str] = None
    common_name: Optional[str] = None
    common_name_source: Optional[str] = None
    genus: Optional[str] = None
    species: Optional[str] = None
    infraspecific_epithet: Optional[str] = None
    culture_or_strain_id: Optional[str] = None
    authority: Optional[str] = None
    atol_scientific_name: Optional[str] = None
    tax_string: Optional[str] = None
    ncbi_order: Optional[str] = None
    ncbi_family: Optional[str] = None
    busco_dataset_name: Optional[str] = None
    augustus_dataset_name: Optional[str] = None
    bpa_json: Optional[Dict] = None
    taxonomy_lineage_json: Optional[Dict] = None


# Schema for organism in DB
class OrganismInDBBase(OrganismBase):
    """Base schema for Organism in DB, includes id and timestamps."""

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# Schema for returning organism information
class Organism(OrganismInDBBase):
    """Schema for returning organism information."""

    pass

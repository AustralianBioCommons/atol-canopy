from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.taxonomy_info import TaxonomyInfo as TaxonomyInfoSchema


class OrganismBase(BaseModel):
    """Base Organism schema with common attributes."""

    taxon_id: int
    bpa_scientific_name: Optional[str] = None
    bpa_genus: Optional[str] = None
    bpa_species: Optional[str] = None
    bpa_common_name: Optional[str] = None
    bpa_infraspecific_epithet: Optional[str] = None
    bpa_culture_or_strain_id: Optional[str] = None
    bpa_authority: Optional[str] = None
    scientific_name: Optional[str] = None
    atol_scientific_name: Optional[str] = None
    bpa_json: Optional[Dict] = None


class OrganismCreate(OrganismBase):
    """Schema for creating a new organism."""

    pass


class OrganismUpdate(BaseModel):
    """Schema for updating an existing organism."""

    bpa_scientific_name: Optional[str] = None
    bpa_genus: Optional[str] = None
    bpa_species: Optional[str] = None
    bpa_common_name: Optional[str] = None
    bpa_infraspecific_epithet: Optional[str] = None
    bpa_culture_or_strain_id: Optional[str] = None
    bpa_authority: Optional[str] = None
    scientific_name: Optional[str] = None
    atol_scientific_name: Optional[str] = None
    bpa_json: Optional[Dict] = None


class OrganismInDBBase(OrganismBase):
    """Base schema for Organism in DB, includes id and timestamps."""

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Organism(OrganismInDBBase):
    """Schema for returning organism information."""

    taxonomy_info: Optional[TaxonomyInfoSchema] = None

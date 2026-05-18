from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

from pydantic import BaseModel, ConfigDict, model_validator

from app.schemas.taxonomy_info import TaxonomyInfo as TaxonomyInfoSchema


class OrganismWriteBase(BaseModel):
    bpa_scientific_name: Optional[str] = None
    bpa_genus: Optional[str] = None
    bpa_species: Optional[str] = None
    bpa_common_name: Optional[str] = None
    bpa_infraspecific_epithet: Optional[str] = None
    bpa_culture_or_strain_id: Optional[str] = None
    bpa_authority: Optional[str] = None
    bpa_json: Optional[Dict] = None

    # TODO this is for backwards compatability - we can change this once we update the data mapper field names
    @model_validator(mode="before")
    @classmethod
    def _coerce_scientific_name(cls, data):
        if isinstance(data, dict) and "bpa_scientific_name" not in data and "scientific_name" in data:
            data = dict(data)
            data["bpa_scientific_name"] = data["scientific_name"]
        return data


class OrganismBase(BaseModel):
    """Base Organism schema with common attributes."""

    taxon_id: int
    scientific_name: Optional[str] = None
    bpa_scientific_name: Optional[str] = None
    bpa_genus: Optional[str] = None
    bpa_species: Optional[str] = None
    bpa_common_name: Optional[str] = None
    bpa_infraspecific_epithet: Optional[str] = None
    bpa_culture_or_strain_id: Optional[str] = None
    bpa_authority: Optional[str] = None
    bpa_json: Optional[Dict] = None


class OrganismCreate(OrganismWriteBase):
    """Schema for creating a new organism."""

    taxon_id: int


class OrganismUpdate(OrganismWriteBase):
    """Schema for updating an existing organism."""


class OrganismInDBBase(OrganismBase):
    """Base schema for Organism in DB, includes id and timestamps."""

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Organism(OrganismInDBBase):
    """Schema for returning organism information."""

    taxonomy_info: Optional[TaxonomyInfoSchema] = None

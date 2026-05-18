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
        # TODO: Remove this legacy field mapping once all callers send bpa_* organism fields.
        if not isinstance(data, dict):
            return data

        legacy_to_bpa = {
            "scientific_name": "bpa_scientific_name",
            "genus": "bpa_genus",
            "species": "bpa_species",
            "common_name": "bpa_common_name",
            "infraspecific_epithet": "bpa_infraspecific_epithet",
            "culture_or_strain_id": "bpa_culture_or_strain_id",
            "authority": "bpa_authority",
        }

        needs_copy = any(
            bpa_field not in data and legacy_field in data
            for legacy_field, bpa_field in legacy_to_bpa.items()
        )
        if needs_copy:
            data = dict(data)
            for legacy_field, bpa_field in legacy_to_bpa.items():
                if bpa_field not in data and legacy_field in data:
                    data[bpa_field] = data[legacy_field]
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

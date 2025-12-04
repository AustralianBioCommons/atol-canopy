from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


# Base BPA Initiative schema
class BPAInitiativeBase(BaseModel):
    """Base BPA Initiative schema with common attributes."""
    name: str
    shipment_accession: Optional[str] = None


# Schema for creating a new BPA Initiative
class BPAInitiativeCreate(BPAInitiativeBase):
    """Schema for creating a new BPA Initiative."""
    pass


# Schema for updating an existing BPA Initiative
class BPAInitiativeUpdate(BaseModel):
    """Schema for updating an existing BPA Initiative."""
    name: Optional[str] = None
    shipment_accession: Optional[str] = None


# Schema for BPA Initiative in DB
class BPAInitiativeInDBBase(BPAInitiativeBase):
    """Base schema for BPA Initiative in DB, includes id and timestamps."""
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Schema for returning BPA Initiative information
class BPAInitiative(BPAInitiativeInDBBase):
    """Schema for returning BPA Initiative information."""
    pass

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator


class TolidRequestStatus(str, Enum):
    NOT_REQUESTED = "not_requested"
    PENDING = "pending"
    ASSIGNED = "assigned"
    FAILED = "failed"


class TolidRequestBrokerView(BaseModel):
    sample_id: UUID
    specimen_id: Optional[str] = None
    tolid_external_id: str
    taxon_id: int
    scientific_name: Optional[str] = None
    status: TolidRequestStatus
    request_id: Optional[str] = None
    tolid: Optional[str] = None
    last_requested_at: Optional[datetime] = None
    error_message: Optional[str] = None


class TolidRequestReport(BaseModel):
    status: TolidRequestStatus
    tolid: Optional[str] = None
    request_id: Optional[str] = None
    last_requested_at: Optional[datetime] = None
    error_message: Optional[str] = None

    @model_validator(mode="after")
    def _validate_status_requirements(self):
        if self.status == TolidRequestStatus.NOT_REQUESTED:
            raise ValueError("status must be one of pending, assigned, or failed")
        if self.status == TolidRequestStatus.ASSIGNED and not self.tolid:
            raise ValueError("assigned status requires tolid")
        if self.status == TolidRequestStatus.PENDING and not self.request_id:
            raise ValueError("pending status requires request_id")
        return self


class TolidRequestInDB(BaseModel):
    id: UUID
    sample_id: UUID
    tolid_external_id: str
    taxon_id: int
    scientific_name: Optional[str] = None
    tolid: Optional[str] = None
    request_id: Optional[str] = None
    status: TolidRequestStatus
    last_requested_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BrokerEntityType(str, Enum):
    PROJECT = "project"
    SAMPLE = "sample"
    EXPERIMENT = "experiment"
    RUN = "run"


class BrokerPrerequisites(BaseModel):
    # Existing accessions (already submitted and available)
    project_accession: Optional[str] = None
    sample_accession: Optional[str] = None
    experiment_accession: Optional[str] = None
    run_accession: Optional[str] = None
    study_accession: Optional[str] = None
    analysis_accession: Optional[str] = None


class BrokerFileMetadata(BaseModel):
    filename: str
    filetype: str


class BrokerClaimEntity(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    type: BrokerEntityType
    id: UUID
    tax_id: str
    scientific_name: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    prerequisites: Optional[BrokerPrerequisites] = None
    files: Optional[List[BrokerFileMetadata]] = None
    file_metadata: Optional[List[BrokerFileMetadata]] = None


class BrokerReadyClaimRequest(BaseModel):
    tax_id: str


class BrokerReadyClaimResponse(BaseModel):
    attempt_id: Optional[UUID]
    tax_id: str
    scope: str = "full"
    entities: List[BrokerClaimEntity] = Field(default_factory=list)


class BrokerTargetedClaimRequest(BaseModel):
    entity_type: BrokerEntityType
    entity_id: UUID


class BrokerTargetedClaimResponse(BaseModel):
    attempt_id: UUID
    tax_id: str
    entities: List[BrokerClaimEntity] = Field(default_factory=list)


class BrokerBatchClaimRequest(BaseModel):
    project_ids: List[UUID] = Field(default_factory=list)
    sample_ids: List[UUID] = Field(default_factory=list)
    experiment_ids: List[UUID] = Field(default_factory=list)
    run_ids: List[UUID] = Field(default_factory=list)


class BrokerBatchClaimResponse(BaseModel):
    attempt_id: UUID
    tax_id: Optional[str] = None  # None if multi-organism batch
    entities: List[BrokerClaimEntity] = Field(default_factory=list)


class BrokerValidationIssue(BaseModel):
    field: str
    message: str


class BrokerValidationRequest(BaseModel):
    entity_type: BrokerEntityType
    entity_id: UUID
    overrides: BrokerPrerequisites = Field(default_factory=BrokerPrerequisites)


class BrokerValidationResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    entity_type: BrokerEntityType
    entity_id: UUID
    valid: bool
    issues: List[BrokerValidationIssue] = Field(default_factory=list)
    resolved_prerequisites: Dict[str, str] = Field(default_factory=dict)


class BrokerReportRecord(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    entity_type: BrokerEntityType
    entity_id: UUID
    status: (
        str  # "completed"/"accepted"/"success" -> accepted, "failed"/"rejected"/"error" -> rejected
    )
    accession: Optional[str] = None  # Primary/ENA accession (internal ENA ID)
    secondary_accession: Optional[str] = None  # Public accession (SAMEA*, PRJEB*, etc.)
    receipt_path: Optional[str] = None
    message: Optional[str] = None
    errors: List[Any] = Field(default_factory=list)
    response_payload: Optional[Dict[str, Any]] = None  # Full ENA response


class BrokerReportRequest(BaseModel):
    tax_id: Optional[str | int] = None
    results: List[BrokerReportRecord] = Field(default_factory=list)


class BrokerReportResponse(BaseModel):
    attempt_id: UUID
    accepted: bool
    message: str

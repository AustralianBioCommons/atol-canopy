from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, field_validator, model_validator

_MD5_RE = re.compile(r"^[a-f0-9]{32}$")
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")

FileType = Literal["cram", "fastq_r1", "fastq_r2"]


# ---------------------------------------------------------------------------
# QC callback payload (genome launcher → Canopy)
# ---------------------------------------------------------------------------


class QcFileInput(BaseModel):
    file_type: FileType
    storage_backend: str
    storage_profile: str
    bucket_name: str
    path_to_file: str
    md5_checksum: str
    sha256_checksum: str

    @field_validator("md5_checksum")
    @classmethod
    def validate_md5(cls, v: str) -> str:
        if not _MD5_RE.match(v):
            raise ValueError("md5_checksum must be 32 lowercase hex characters")
        return v

    @field_validator("sha256_checksum")
    @classmethod
    def validate_sha256(cls, v: str) -> str:
        if not _SHA256_RE.match(v):
            raise ValueError("sha256_checksum must be 64 lowercase hex characters")
        return v


class QcCallbackRequest(BaseModel):
    """Payload posted by the genome launcher after QC completes."""

    bpa_package_id: str
    base_count: int
    read_count: int
    qc_bases_removed: int
    qc_reads_removed: int
    mean_gc_content: float
    n50_length: Optional[int] = None
    files: List[QcFileInput]

    @model_validator(mode="after")
    def validate_file_set(self) -> "QcCallbackRequest":
        types = {f.file_type for f in self.files}
        is_cram = types == {"cram"} and len(self.files) == 1
        is_fastq_pair = types == {"fastq_r1", "fastq_r2"} and len(self.files) == 2
        if not (is_cram or is_fastq_pair):
            raise ValueError(
                "files must be either exactly one CRAM file or exactly one fastq_r1 + one fastq_r2"
            )
        return self


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class QcReadFileOut(BaseModel):
    id: UUID
    qc_read_id: UUID
    file_type: str
    storage_backend: str
    storage_profile: str
    bucket_name: str
    path_to_file: str
    md5_checksum: str
    sha256_checksum: str
    created_at: datetime

    model_config = {"from_attributes": True}


class QcReadSubmissionOut(BaseModel):
    id: UUID
    qc_read_id: UUID
    experiment_id: Optional[UUID]
    authority: str
    status: str
    accession: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class QcReadOut(BaseModel):
    id: UUID
    experiment_id: UUID
    base_count: int
    read_count: int
    qc_bases_removed: int
    qc_reads_removed: int
    mean_gc_content: float
    n50_length: Optional[int]
    created_at: datetime
    updated_at: datetime
    files: List[QcReadFileOut] = []
    submission_records: List[QcReadSubmissionOut] = []

    model_config = {"from_attributes": True}

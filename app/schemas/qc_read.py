from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, field_validator, model_validator

_MD5_RE = re.compile(r"^[a-f0-9]{32}$")
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
_FASTQ_EXT_RE = re.compile(r"\.(fastq|fq)(?:\.gz)?$", re.IGNORECASE)
_CRAM_EXT_RE = re.compile(r"\.cram$", re.IGNORECASE)
_FASTQ_R1_RE = re.compile(r"(^|[._-])(r?1|read1)([._-]|$)", re.IGNORECASE)
_FASTQ_R2_RE = re.compile(r"(^|[._-])(r?2|read2)([._-]|$)", re.IGNORECASE)

FileType = Literal["cram", "fastq", "fastq_r1", "fastq_r2"]


# ---------------------------------------------------------------------------
# QC callback payload (genome launcher → Canopy)
# ---------------------------------------------------------------------------


class QcFileChecksums(BaseModel):
    md5: str
    sha256: str

    @field_validator("md5")
    @classmethod
    def validate_md5(cls, v: str) -> str:
        if not _MD5_RE.match(v):
            raise ValueError("md5 must be 32 lowercase hex characters")
        return v

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, v: str) -> str:
        if not _SHA256_RE.match(v):
            raise ValueError("sha256 must be 64 lowercase hex characters")
        return v


class ClassifiedQcFile(BaseModel):
    file_name: str
    file_type: FileType
    md5: str
    sha256: str


def classify_reported_files(checksums: Dict[str, QcFileChecksums]) -> List[ClassifiedQcFile]:
    items = list(checksums.items())
    if len(items) == 1:
        file_name, checksum = items[0]
        if _CRAM_EXT_RE.search(file_name):
            file_type: FileType = "cram"
        elif _FASTQ_EXT_RE.search(file_name):
            file_type = "fastq"
        else:
            raise ValueError(
                "single-file QC reports must use a .cram, .fastq, .fastq.gz, .fq, or .fq.gz filename"
            )
        return [
            ClassifiedQcFile(
                file_name=file_name,
                file_type=file_type,
                md5=checksum.md5,
                sha256=checksum.sha256,
            )
        ]

    if len(items) != 2:
        raise ValueError("checksums must contain either one file or exactly one paired FASTQ set")

    classified: List[ClassifiedQcFile] = []
    seen_types: set[FileType] = set()
    for file_name, checksum in items:
        if not _FASTQ_EXT_RE.search(file_name):
            raise ValueError("paired QC reports must use FASTQ filenames")
        if _FASTQ_R1_RE.search(file_name):
            file_type = "fastq_r1"
        elif _FASTQ_R2_RE.search(file_name):
            file_type = "fastq_r2"
        else:
            raise ValueError(
                "paired FASTQ filenames must identify read direction with R1/read1 and R2/read2"
            )
        seen_types.add(file_type)
        classified.append(
            ClassifiedQcFile(
                file_name=file_name,
                file_type=file_type,
                md5=checksum.md5,
                sha256=checksum.sha256,
            )
        )

    if seen_types != {"fastq_r1", "fastq_r2"}:
        raise ValueError("paired QC reports must include exactly one R1 FASTQ and one R2 FASTQ")

    return classified


class QcCallbackRequest(BaseModel):
    """Payload posted by the genome launcher after QC completes for one QC read-set."""

    bpa_package_id: str
    source_read_file_checksums: List[str]
    base_count: int
    read_count: int
    qc_bases_removed: int
    qc_reads_removed: int
    mean_gc_content: float
    n50_length: Optional[int] = None
    checksums: Dict[str, QcFileChecksums]

    @model_validator(mode="after")
    def validate_file_set(self) -> "QcCallbackRequest":
        if not self.bpa_package_id.strip():
            raise ValueError("bpa_package_id must not be empty")
        if not (1 <= len(self.source_read_file_checksums) <= 2):
            raise ValueError("source_read_file_checksums must contain one or two MD5 sums")
        if len(set(self.source_read_file_checksums)) != len(self.source_read_file_checksums):
            raise ValueError("source_read_file_checksums must not contain duplicates")
        for md5sum in self.source_read_file_checksums:
            if not _MD5_RE.match(md5sum):
                raise ValueError(
                    "source_read_file_checksums entries must be 32 lowercase hex characters"
                )
        classify_reported_files(self.checksums)
        return self


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class QcReadFileOut(BaseModel):
    id: UUID
    qc_read_id: UUID
    file_type: str
    file_name: str
    md5: str
    sha256: str
    created_at: datetime

    model_config = {"from_attributes": True}


class QcReadSubmissionOut(BaseModel):
    id: UUID
    qc_read_id: UUID
    authority: str
    status: str
    accession: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class QcReadOut(BaseModel):
    id: UUID
    experiment_id: UUID
    source_read_file_checksums: List[str]
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


class QcReadDetail(QcReadOut):
    """Detailed QC read schema used by nested aggregate endpoints."""

    pass

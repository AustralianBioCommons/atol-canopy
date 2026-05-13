"""QC read endpoints — CRUD and genome launcher report callback."""

from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_active_user, get_db
from app.core.pagination import Pagination, apply_pagination, pagination_params
from app.core.policy import policy
from app.models.experiment import Experiment
from app.models.qc_read import QcRead, QcReadFile, QcReadSubmission
from app.models.user import User
from app.schemas.qc_read import QcCallbackRequest, QcReadOut

router = APIRouter()


def _build_prepared_payload(qc_read: QcRead, files: list[QcReadFile]) -> dict:
    """Build the ENA submission payload stored on QcReadSubmission."""
    return {
        "files": [
            {
                "filename": f.path_to_file,
                "filetype": f.file_type.replace("_r1", "").replace("_r2", ""),
                "checksum": f.md5_checksum,
                "checksum_method": "MD5",
            }
            for f in files
        ]
    }


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


@router.get("/", response_model=List[QcReadOut])
def list_qc_reads(
    db: Session = Depends(get_db),
    pagination: Pagination = Depends(pagination_params),
    experiment_id: Optional[UUID] = Query(None, description="Filter by experiment ID"),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """List QC reads, optionally filtered by experiment."""
    query = db.query(QcRead)
    if experiment_id:
        query = query.filter(QcRead.experiment_id == experiment_id)
    return apply_pagination(query, pagination).all()


@router.get("/{qc_read_id}", response_model=QcReadOut)
def get_qc_read(
    *,
    db: Session = Depends(get_db),
    qc_read_id: UUID,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Get a single QC read by ID, including its files and submission records."""
    qc_read = db.query(QcRead).filter(QcRead.id == qc_read_id).first()
    if not qc_read:
        raise HTTPException(status_code=404, detail="QC read not found")
    return qc_read


@router.delete("/{qc_read_id}", response_model=QcReadOut)
@policy("qc_reads:delete")
def delete_qc_read(
    *,
    db: Session = Depends(get_db),
    qc_read_id: UUID,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Delete a QC read and its associated files and submission records."""
    qc_read = db.query(QcRead).filter(QcRead.id == qc_read_id).first()
    if not qc_read:
        raise HTTPException(status_code=404, detail="QC read not found")
    db.delete(qc_read)
    db.commit()
    return qc_read


# ---------------------------------------------------------------------------
# Genome launcher callback
# ---------------------------------------------------------------------------


@router.post("/report", response_model=QcReadOut, status_code=201)
@policy("qc_reads:report")
def report_qc_result(
    *,
    payload: QcCallbackRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> QcRead:
    """Accept a QC result from the genome launcher and create submission records.

    The genome launcher identifies the target experiment by ``bpa_package_id``.
    On success, ``qc_read``, ``qc_read_file``, and ``qc_read_submission`` rows
    are created atomically and the ``qc_read`` is returned.
    """
    experiment = (
        db.query(Experiment).filter(Experiment.bpa_package_id == payload.bpa_package_id).first()
    )
    if not experiment:
        raise HTTPException(
            status_code=404,
            detail=f"Experiment with bpa_package_id '{payload.bpa_package_id}' not found",
        )

    qc_read = QcRead(
        experiment_id=experiment.id,
        base_count=payload.base_count,
        read_count=payload.read_count,
        qc_bases_removed=payload.qc_bases_removed,
        qc_reads_removed=payload.qc_reads_removed,
        mean_gc_content=payload.mean_gc_content,
        n50_length=payload.n50_length,
    )
    db.add(qc_read)
    db.flush()

    qc_files = [
        QcReadFile(
            qc_read_id=qc_read.id,
            file_type=f.file_type,
            storage_backend=f.storage_backend,
            storage_profile=f.storage_profile,
            bucket_name=f.bucket_name,
            path_to_file=f.path_to_file,
            md5_checksum=f.md5_checksum,
            sha256_checksum=f.sha256_checksum,
        )
        for f in payload.files
    ]
    for qf in qc_files:
        db.add(qf)
    db.flush()

    prepared_payload = _build_prepared_payload(qc_read, qc_files)

    submission = QcReadSubmission(
        qc_read_id=qc_read.id,
        experiment_id=experiment.id,
        authority="ENA",
        status="draft",
        prepared_payload=prepared_payload,
        entity_type_const="qc_read",
    )
    db.add(submission)
    db.commit()
    db.refresh(qc_read)
    return qc_read

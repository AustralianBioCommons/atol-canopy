"""QC read endpoints — CRUD."""

from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_active_user, get_db
from app.core.pagination import Pagination, apply_pagination, pagination_params
from app.core.policy import policy
from app.models.qc_read import QcRead, QcReadAssembly, QcReadFile, QcReadSubmission
from app.models.user import User
from app.schemas.qc_read import QcReadOut

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
    assembly_id: Optional[UUID] = Query(None, description="Filter by assembly ID"),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """List QC reads, optionally filtered by experiment or assembly."""
    query = db.query(QcRead)
    if experiment_id:
        query = query.filter(QcRead.experiment_id == experiment_id)
    if assembly_id:
        query = query.join(QcReadAssembly).filter(QcReadAssembly.assembly_id == assembly_id)
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

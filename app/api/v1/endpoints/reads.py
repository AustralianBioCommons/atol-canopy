import json
import uuid
import os
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import (
    get_current_active_user,
    get_current_superuser,
    get_db,
    require_role,
)
from app.models.read import Read, ReadSubmission
from app.models.user import User
from app.schemas.read import (
    Read as ReadSchema,
    ReadCreate,
    ReadUpdate,
)
from app.schemas.common import SubmissionJsonResponse, SubmissionStatus

router = APIRouter()


@router.get("/", response_model=List[ReadSchema])
def read_reads(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    experiment_id: Optional[UUID] = Query(None, description="Filter by experiment ID"),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Retrieve reads.
    """
    # All users can read reads
    query = db.query(Read)
    if experiment_id:
        query = query.filter(Read.experiment_id == experiment_id)
    
    reads = query.offset(skip).limit(limit).all()
    return reads


@router.post("/", response_model=ReadSchema)
def create_read(
    *,
    db: Session = Depends(get_db),
    read_in: ReadCreate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Create new read.
    """
    # Only users with 'curator' or 'admin' role can create reads
    require_role(current_user, ["curator", "admin"])
    read_id = uuid.uuid4()
    
    read = Read(
        id=read_id,
        experiment_id=read_in.experiment_id,
        bpa_resource_id=read_in.bpa_resource_id,
        bpa_json=read_in.model_dump(mode="json", exclude_unset=True),
        file_name=read_in.file_name,
        file_checksum=read_in.file_checksum,
        file_format=read_in.file_format,
        file_submission_date=read_in.file_submission_date,
        optional_file=read_in.optional_file,
        bioplatforms_url=read_in.bioplatforms_url,
        reads_access_date=read_in.reads_access_date,
        read_number=read_in.read_number,
        lane_number=read_in.lane_number,
        sra_run_accession=read_in.sra_run_accession,
        run_read_count=read_in.run_read_count,
        run_base_count=read_in.run_base_count,
    )
    db.add(read)
    
    read_data = read_in.dict(exclude_unset=True)
    # Load the ENA-ATOL mapping file
    ena_atol_map_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "config", "ena-atol-map.json")
    with open(ena_atol_map_path, "r") as f:
        ena_atol_map = json.load(f)
    # Generate ENA-mapped data for submission to ENA
    prepared_payload = {}
    for ena_key, atol_key in ena_atol_map["run"].items():
        if atol_key in read_data:
            prepared_payload[ena_key] = read_data[atol_key]

    read_submission = ReadSubmission(
        read_id=read_id,
        experiment_id=read_in.experiment_id,
        project_id=read_in.project_id,
        entity_type_const="read",
        prepared_payload=prepared_payload,
        status=SubmissionStatus.DRAFT,
    )
    db.add(read_submission)
    db.commit()
    db.refresh(read)
    db.refresh(read_submission)
    return read


@router.get("/{read_id}/prepared-payload", response_model=SubmissionJsonResponse)
def get_read_prepared_payload(
    *,
    db: Session = Depends(get_db),
    read_id: UUID,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get prepared_payload for a specific read submission.
    """
    read_submission = db.query(ReadSubmission).filter(ReadSubmission.read_id == read_id).first()
    if not read_submission:
        raise HTTPException(
            status_code=404,
            detail="Read submission not found",
        )
    if not read_submission.prepared_payload:
        raise HTTPException(
            status_code=404,
            detail="Prepared payload not found for this read submission",
        )
    return {"submission_json": read_submission.prepared_payload}


@router.get("/{read_id}", response_model=ReadSchema)
def read_read(
    *,
    db: Session = Depends(get_db),
    read_id: UUID,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get read by ID.
    """
    # All users can read read details
    read = db.query(Read).filter(Read.id == read_id).first()
    if not read:
        raise HTTPException(status_code=404, detail="Read not found")
    return read


@router.put("/{read_id}", response_model=ReadSchema)
def update_read(
    *,
    db: Session = Depends(get_db),
    read_id: UUID,
    read_in: ReadUpdate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Update a read.
    """
    # Only users with 'curator' or 'admin' role can update reads
    require_role(current_user, ["curator", "admin"])
    
    read = db.query(Read).filter(Read.id == read_id).first()
    if not read:
        raise HTTPException(status_code=404, detail="Read not found")
    
    update_data = read_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(read, field, value)
    
    db.add(read)
    db.commit()
    db.refresh(read)
    return read


@router.delete("/{read_id}", response_model=ReadSchema)
def delete_read(
    *,
    db: Session = Depends(get_db),
    read_id: UUID,
    current_user: User = Depends(get_current_superuser),
) -> Any:
    """
    Delete a read.
    """
    # Only superusers can delete reads
    read = db.query(Read).filter(Read.id == read_id).first()
    if not read:
        raise HTTPException(status_code=404, detail="Read not found")
    
    db.delete(read)
    db.commit()
    return read

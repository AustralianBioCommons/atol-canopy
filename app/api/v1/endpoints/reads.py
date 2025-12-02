import json
import uuid
import os
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

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
    
    # Auto-map from Pydantic schema to Read columns
    read_data = read_in.model_dump(exclude_unset=True)
    allowed_cols = {c.name for c in Read.__table__.columns}
    exclude_keys = {"id", "created_at", "updated_at", "bpa_json"}
    read_kwargs = {k: v for k, v in read_data.items() if k in (allowed_cols - exclude_keys)}
    # Normalize optional_file if present
    if "optional_file" in read_kwargs and read_kwargs["optional_file"] is not None:
        val = read_kwargs["optional_file"]
        if not isinstance(val, bool):
            read_kwargs["optional_file"] = str(val).lower() in ("true", "1", "yes")

    read = Read(
        id=read_id,
        #bpa_json=read_data,
        **read_kwargs,
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
    return {"prepared_payload": read_submission.prepared_payload}


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
    
    read_submission = db.query(ReadSubmission).filter(ReadSubmission.read_id == read_id).order_by(ReadSubmission.updated_at.desc()).first()
    new_read_submission = None
    latest_read_submission = None
    if not read_submission:
        new_read_submission = ReadSubmission(
            read_id=read_id,
            experiment_id=read_in.experiment_id,
            project_id=read_in.project_id,
            entity_type_const="read",
            prepared_payload=prepared_payload,
            status=SubmissionStatus.DRAFT,
        )
        db.add(new_read_submission)
    else:
        latest_read_submission = read_submission
        if latest_read_submission.status == "submitting":
                raise HTTPException(status_code=404, detail=f"Read with id: {read_id} is currently being submitted to ENA and could not be updated. Please try again later.")
        elif latest_read_submission.status == "rejected" or read_submission.status == "replaced":
            # leave the old record for logs and create a new record
            # retain accessions if they exist (accessions may not exist if status is 'rejected' and the sample has not successfully been submitted in the past)
            new_read_submission = ReadSubmission(
                read_id=read_id,
                experiment_id=read_in.experiment_id,
                project_id=read_in.project_id,
                authority=read_submission.authority,
                entity_type_const="read",
                prepared_payload=prepared_payload,
                response_payload=None,
                accession=experiment_submission.accession,
                biosample_accession=experiment_submission.biosample_accession,
                status="draft",
            )
            db.add(new_read_submission)
            
        elif latest_read_submission.status == "accepted":
            # change old record's status to "replaced" and create a new record
            # retain accessions
            setattr(latest_read_submission, "status", "replaced")
            db.add(latest_read_submission)
            new_read_submission = ReadSubmission(
                read_id=read_id,
                experiment_id=read_in.experiment_id,
                project_id=read_in.project_id,
                authority=read_submission.authority,
                entity_type_const="read",
                prepared_payload=prepared_payload,
                response_payload=None,
                accession=experiment_submission.accession,
                biosample_accession=experiment_submission.biosample_accession,
                status="draft",
            )
            db.add(new_read_submission)
        elif latest_read_submission.status == "draft" or latest_read_submission.status == "ready":
            # update the existing record, since it has not yet been submitted to ENA (set status = 'draft')
            setattr(latest_read_submission, "prepared_payload", prepared_payload)
            setattr(latest_read_submission, "status", "draft")
            db.add(latest_read_submission)
            # update the experiment_submission object
    
    setattr(read, "bpa_resource_id", read_in.bpa_resource_id)
    setattr(read, "experiment_id", read_in.experiment_id)
    setattr(read, "project_id", read_in.project_id)
    # initiate new bpa_json object to the previous bpa_json object
    """
    new_bpa_json = read.bpa_json

    for field, value in read_data.items():
        if field != "experiment_id" and field != "project_id":
            new_bpa_json[field] = value
    read.bpa_json = new_bpa_json
    flag_modified(read, "bpa_json")
    """
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

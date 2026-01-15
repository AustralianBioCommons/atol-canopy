import json
import os
import uuid
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
from app.models.experiment import Experiment
from app.models.organism import Organism
from app.models.sample import Sample, SampleSubmission
from app.models.user import User
from app.schemas.bulk_import import BulkImportResponse, BulkSampleImport
from app.schemas.common import SubmissionJsonResponse
from app.schemas.sample import (
    Sample as SampleSchema,
)
from app.schemas.sample import (
    SampleCreate,
    SampleSubmissionCreate,
    SampleSubmissionUpdate,
    SampleUpdate,
)
from app.schemas.sample import (
    SampleSubmission as SampleSubmissionSchema,
)
from app.schemas.sample import (
    SubmissionStatus as SchemaSubmissionStatus,
)

router = APIRouter()


@router.get("/", response_model=List[SampleSubmissionSchema])
def read_sample_submissions(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    status: Optional[SchemaSubmissionStatus] = Query(
        None, description="Filter by submission status"
    ),
    # sample_id: Optional[str] = Query(None, description="Filter by sample_id"),
    # organism_key: Optional[str] = Query(None, description="Filter by organism_key"),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Retrieve sample submissions.
    """
    # Admin, curator, broker and genome_launcher can get submission data
    require_role(current_user, ["admin", "curator", "broker", "genome_launcher"])

    query = db.query(SampleSubmission)
    if status:
        query = query.filter(SampleSubmission.status == status)

    submissions = query.offset(skip).limit(limit).all()
    return submissions


@router.get("/{submission_id}", response_model=SampleSubmissionSchema)
def read_sample_submissions(
    submission_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Retrieve sample submissions.
    """
    # Admin, curator, broker and genome_launcher can get submission data
    require_role(current_user, ["admin", "curator", "broker", "genome_launcher"])

    submission = db.query(SampleSubmission).filter(SampleSubmission.id == submission_id).first()
    if not submission:
        raise HTTPException(
            status_code=404, detail="Sample submission not found for sample: {sample_id}"
        )
    return submission


@router.post("/", response_model=SampleSubmissionSchema)
def create_sample_submission(
    *,
    db: Session = Depends(get_db),
    submission_in: SampleSubmissionCreate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Create new sample submission.
    """
    # Only users with 'curator' or 'admin' role can create sample submissions
    require_role(current_user, ["curator", "admin"])

    submission = SampleSubmission(
        sample_id=submission_in.sample_id,
        authority=submission_in.authority,
        entity_type_const=submission_in.entity_type_const,
        prepared_payload=submission_in.prepared_payload,
        response_payload=submission_in.response_payload,
        accession=submission_in.accession,
        biosample_accession=submission_in.biosample_accession,
        status=submission_in.status,
        submitted_at=submission_in.submitted_at,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return submission


"""
@router.put("/{submission_id}", response_model=SampleSubmissionSchema)
def update_sample_submission(
    *,
    db: Session = Depends(get_db),
    submission_id: UUID,
    submission_in: SampleSubmissionUpdate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    # Update a sample submission.
    # Only users with 'curator' or 'admin' role can update sample submissions
    require_role(current_user, ["curator", "admin"])

    submission = db.query(SampleSubmission).filter(SampleSubmission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Sample submission not found")

    update_data = submission_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(submission, field, value)

    db.add(submission)
    db.commit()
    db.refresh(submission)
    return submission
"""

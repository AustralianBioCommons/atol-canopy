from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_active_user, get_db
from app.core.pagination import Pagination, apply_pagination, pagination_params
from app.core.policy import policy
from app.models.project import Project
from app.models.sample import Sample, SampleSubmission
from app.models.user import User
from app.schemas.sample import (
    SampleSubmission as SampleSubmissionSchema,
)
from app.schemas.sample import (
    SampleSubmissionCreate,
)
from app.schemas.sample import (
    SubmissionStatus as SchemaSubmissionStatus,
)

router = APIRouter()


def _resolve_sample_submission_project_id(db: Session, sample_id: UUID) -> UUID:
    sample = db.query(Sample).filter(Sample.id == sample_id).first()
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found")

    project = (
        db.query(Project)
        .filter(
            Project.taxon_id == sample.taxon_id,
            Project.project_type == "genomic_data",
        )
        .first()
    )
    if not project:
        raise HTTPException(
            status_code=404,
            detail=f"No genomic_data project found for taxon_id '{sample.taxon_id}'",
        )
    return project.id


@router.get("/", response_model=List[SampleSubmissionSchema])
@policy("sample_submissions:read")
def read_sample_submissions(
    db: Session = Depends(get_db),
    pagination: Pagination = Depends(pagination_params),
    status: Optional[SchemaSubmissionStatus] = Query(
        None, description="Filter by submission status"
    ),
    # sample_id: Optional[str] = Query(None, description="Filter by sample_id"),
    # taxon_id: Optional[str] = Query(None, description="Filter by taxon_id"),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Retrieve sample submissions.
    """
    query = db.query(SampleSubmission)
    if status:
        query = query.filter(SampleSubmission.status == status)

    submissions = apply_pagination(query, pagination).all()
    return submissions


@router.get("/{submission_id}", response_model=SampleSubmissionSchema)
@policy("sample_submissions:read")
def read_sample_submission(
    submission_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Retrieve sample submissions.
    """
    submission = db.query(SampleSubmission).filter(SampleSubmission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Sample submission not found")
    return submission


@router.post("/", response_model=SampleSubmissionSchema)
@policy("sample_submissions:write")
def create_sample_submission(
    *,
    db: Session = Depends(get_db),
    submission_in: SampleSubmissionCreate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Create new sample submission.
    """
    submission = SampleSubmission(
        sample_id=submission_in.sample_id,
        authority=submission_in.authority,
        entity_type_const=submission_in.entity_type_const,
        prepared_payload=submission_in.prepared_payload,
        response_payload=submission_in.response_payload,
        accession=submission_in.accession,
        biosample_accession=submission_in.biosample_accession,
        status=submission_in.status,
        project_id=_resolve_sample_submission_project_id(db, submission_in.sample_id),
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

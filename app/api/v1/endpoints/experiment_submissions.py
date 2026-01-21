from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_active_user, get_db, require_role
from app.models.experiment import Experiment, ExperimentSubmission
from app.models.user import User
from app.schemas.bulk_import import BulkExperimentImport, BulkImportResponse
from app.schemas.experiment import (
    Experiment as ExperimentSchema,
)
from app.schemas.experiment import (
    ExperimentSubmission as ExperimentSubmissionSchema,
)
from app.schemas.experiment import (
    ExperimentSubmissionCreate,
    ExperimentSubmissionUpdate,
    SubmissionStatus,
)

router = APIRouter()


# Experiment Submission endpoints
@router.get("/", response_model=List[ExperimentSubmissionSchema])
def read_experiment_submissions(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    status: Optional[SubmissionStatus] = Query(None, description="Filter by submission status"),
    full_history: Optional[bool] = Query(False, description="Return full submission history"),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Retrieve experiment submissions.
    """
    # All users can read experiment submissions
    query = db.query(ExperimentSubmission)
    if status:
        query = query.filter(ExperimentSubmission.status == status)
    if not full_history:
        query = query.order_by(
            ExperimentSubmission.experiment_id,
            ExperimentSubmission.created_at.desc(),
        ).distinct(ExperimentSubmission.experiment_id)

    submissions = query.offset(skip).limit(limit).all()
    return submissions


@router.get("/by-experiment-attr", response_model=List[ExperimentSubmissionSchema])
async def get_experiment_submission_by_experiment_attr(
    db: Session = Depends(get_db),
    bpa_package_id: Optional[str] = Query(None, description="Filter by bpa_package_id"),
    experiment_id: Optional[str] = Query(None, description="Filter by experiment_id"),
    current_user: User = Depends(get_current_active_user),
) -> ExperimentSubmissionSchema:
    """
    Get ExperimentSubmission data for a specific bpa_package_id.

    This endpoint retrieves the submission experiment data associated with a specific BPA package ID.
    """

    query = db.query(Experiment)
    if bpa_package_id:
        query = query.filter(Experiment.bpa_package_id == bpa_package_id)
    if experiment_id:
        query = query.filter(Experiment.id == experiment_id)

    # Find the experiment with the given bpa_package_id
    experiments = query.all()
    if not experiments:
        msg = "Experiment not found"
        if bpa_package_id is not None:
            msg += f" with bpa_package_id: {bpa_package_id}"
        if experiment_id is not None:
            msg += f" or experiment_id: {experiment_id}"
        raise HTTPException(status_code=404, detail=msg)
    experiment_ids = [experiment.id for experiment in experiments]
    # Find the submission record for this experiment
    submission_record = (
        db.query(ExperimentSubmission)
        .filter(ExperimentSubmission.experiment_id.in_(experiment_ids))
        .order_by(
            ExperimentSubmission.experiment_id,  # important: partition key first
            ExperimentSubmission.created_at.desc(),
        )
        .distinct(ExperimentSubmission.experiment_id)  # DISTINCT ON (experiment_id)
        .all()
    )

    if not submission_record:
        msg = "No experiment submission record found"
        if bpa_package_id is not None:
            msg += f" with bpa_package_id: {bpa_package_id}"
        if experiment_id is not None:
            msg += f" or experiment_id: {experiment_id}"
        raise HTTPException(status_code=404, detail=msg)
    return submission_record


@router.get("/{submission_id}", response_model=ExperimentSubmissionSchema)
def read_experiment_submission(
    *,
    db: Session = Depends(get_db),
    submission_id: UUID,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get an experiment submission by ID.
    """
    # All users can read experiment submission details
    submission = (
        db.query(ExperimentSubmission).filter(ExperimentSubmission.id == submission_id).first()
    )
    if not submission:
        raise HTTPException(status_code=404, detail="Experiment submission not found")

    return submission

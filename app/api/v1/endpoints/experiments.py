from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_active_user, get_current_superuser, get_db, require_role
from app.models.user import User
from app.schemas.bulk_import import BulkImportResponse
from app.schemas.experiment import (
    ExperimentCreate,
    Experiment as ExperimentSchema,
    ExperimentUpdate,
    ExperimentSubmission as ExperimentSubmissionSchema
)
from app.services.experiment_service import experiment_service

router = APIRouter()


@router.get("/", response_model=List[ExperimentSchema])
def read_experiments(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    sample_id: Optional[UUID] = Query(None, description="Filter by sample ID"),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Retrieve experiments.
    """
    # All users can read experiments
    return experiment_service.list_experiments(db, skip=skip, limit=limit, sample_id=sample_id)


@router.post("/", response_model=ExperimentSchema)
def create_experiment(
    *,
    db: Session = Depends(get_db),
    experiment_in: ExperimentCreate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Create new experiment.
    """
    # Only users with 'curator' or 'admin' role can create experiments
    require_role(current_user, ["curator", "admin"])
    try:
        experiment = experiment_service.create_experiment(db, experiment_in=experiment_in)
        return experiment
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{experiment_id}/prepared-payload", response_model=ExperimentSubmissionSchema)
def get_experiment_prepared_payload(
    *,
    db: Session = Depends(get_db),
    experiment_id: UUID,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get prepared_payload for a specific experiment.
    """
    submission = experiment_service.get_experiment_prepared_payload(db, experiment_id=experiment_id)
    if not submission:
        raise HTTPException(status_code=404, detail="ExperimentSubmission not found")
    return submission


@router.get("/{experiment_id}", response_model=ExperimentSchema)
def read_experiment(
    *,
    db: Session = Depends(get_db),
    experiment_id: UUID,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get experiment by ID.
    """
    experiment = experiment_service.get(db, experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return experiment


@router.put("/{experiment_id}", response_model=ExperimentSchema)
def update_experiment(
    *,
    db: Session = Depends(get_db),
    experiment_id: UUID,
    experiment_in: ExperimentUpdate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Update an experiment.
    """
    # Only users with 'curator' or 'admin' role can update experiments
    require_role(current_user, ["curator", "admin"])
    try:
        experiment = experiment_service.update_experiment(
            db, experiment_id=experiment_id, experiment_in=experiment_in
        )
        if not experiment:
            raise HTTPException(status_code=404, detail="Experiment not found")
        return experiment
    except RuntimeError as e:
        # Preserve previous semantics for locked/submitting states
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        # Propagate explicit HTTP errors (e.g., 404) without converting to 500
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to update experiment")

@router.delete("/{experiment_id}", response_model=ExperimentSchema)
def delete_experiment(
    *,
    db: Session = Depends(get_db),
    experiment_id: UUID,
    current_user: User = Depends(get_current_superuser),
) -> Any:
    """
    Delete an experiment.
    """
    # Only superusers can delete experiments
    experiment = experiment_service.delete_experiment(db, experiment_id=experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return experiment

@router.post("/bulk-import", response_model=BulkImportResponse)
def bulk_import_experiments(
    *,
    db: Session = Depends(get_db),
    experiments_data: Dict[str, Dict[str, Any]],  # Accept direct dictionary format from experiments.json
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Bulk import experiments from a dictionary keyed by package_id.
    
    The request body should directly match the format of the JSON file in data/experiments.json,
    which is a dictionary keyed by package_id without a wrapping 'experiments' key.
    """
    # Only users with 'curator' or 'admin' role can import experiments
    require_role(current_user, ["curator", "admin"])
    result = experiment_service.bulk_import_experiments(db, experiments_data=experiments_data)
    return result

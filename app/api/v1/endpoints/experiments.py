import json
import uuid
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_active_user, get_current_superuser, get_db, require_role
from app.models.experiment import Experiment, ExperimentSubmission
from app.models.project import Project
from app.models.read import Read, ReadSubmission
from app.models.sample import Sample
from app.models.user import User
from app.schemas.bulk_import import BulkImportResponse
from app.schemas.experiment import (
    ExperimentCreate,
    Experiment as ExperimentSchema,
    ExperimentUpdate,
    ExperimentSubmission as ExperimentSubmissionSchema,
    ExperimentSubmissionCreate,
    ExperimentSubmissionUpdate,
    SubmissionStatus as SchemaSubmissionStatus,
)
from app.schemas.bulk_import import BulkExperimentImport, BulkImportResponse

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
    query = db.query(Experiment)
    if sample_id:
        query = query.filter(Experiment.sample_id == sample_id)
    
    experiments = query.offset(skip).limit(limit).all()
    return experiments


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
    
    experiment = Experiment(
        sample_id=experiment_in.sample_id,
        bpa_package_id=experiment_in.bpa_package_id,
        bpa_json=experiment_in.bpa_json,
    )
    db.add(experiment)
    db.commit()
    db.refresh(experiment)
    return experiment


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
    experiment_submission = db.query(ExperimentSubmission).filter(ExperimentSubmission.experiment_id == experiment_id).first()
    if not experiment_submission:
        raise HTTPException(
            status_code=404,
            detail="Experiment submission data not found",
        )
    return experiment_submission


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
    # All users can read experiment details
    experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
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
    
    experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    
    update_data = experiment_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(experiment, field, value)
    
    db.add(experiment)
    db.commit()
    db.refresh(experiment)
    return experiment


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
    experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    
    db.delete(experiment)
    db.commit()
    return experiment


# Experiment Submission endpoints
@router.get("/submission/", response_model=List[ExperimentSubmissionSchema])
def read_experiment_submissions(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    status: Optional[SchemaSubmissionStatus] = Query(None, description="Filter by submission status"),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Retrieve experiment submissions.
    """
    # All users can read experiment submissions
    query = db.query(ExperimentSubmission)
    if status:
        query = query.filter(ExperimentSubmission.status == status)
    
    submissions = query.offset(skip).limit(limit).all()
    return submissions


@router.post("/submission/", response_model=ExperimentSubmissionSchema)
def create_experiment_submission(
    *,
    db: Session = Depends(get_db),
    submission_in: ExperimentSubmissionCreate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Create new experiment submission.
    """
    # Only users with 'curator' or 'admin' role can create experiment submissions
    require_role(current_user, ["curator", "admin"])
    
    submission = ExperimentSubmission(
        experiment_id=submission_in.experiment_id,
        sample_id=submission_in.sample_id,
        project_id=submission_in.project_id,
        authority=submission_in.authority,
        entity_type_const=submission_in.entity_type_const,
        project_accession=submission_in.project_accession,
        sample_accession=submission_in.sample_accession,
        prepared_payload=submission_in.prepared_payload,
        response_payload=submission_in.response_payload,
        accession=submission_in.accession,
        status=submission_in.status,
        submitted_at=submission_in.submitted_at,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return submission


@router.put("/submission/{submission_id}", response_model=ExperimentSubmissionSchema)
def update_experiment_submission(
    *,
    db: Session = Depends(get_db),
    submission_id: UUID,
    submission_in: ExperimentSubmissionUpdate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Update an experiment submission.
    """
    # Only users with 'curator' or 'admin' role can update experiment submissions
    require_role(current_user, ["curator", "admin"])
    
    submission = db.query(ExperimentSubmission).filter(ExperimentSubmission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Experiment submission not found")
    
    update_data = submission_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(submission, field, value)
    
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return submission


# Experiment Fetched endpoints have been removed as they are no longer in the schema


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
    
    # Load the ENA-ATOL mapping file
    ena_atol_map_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "config", "ena-atol-map.json")
    with open(ena_atol_map_path, "r") as f:
        ena_atol_map = json.load(f)
    
    # Get the experiment mapping section
    experiment_mapping = ena_atol_map.get("experiment", {})
    run_mapping = ena_atol_map.get("run", {})
    
    created_experiments_count = 0
    created_submission_count = 0
    created_reads_count = 0
    skipped_experiments_count = 0
    skipped_runs_count = 0
    
    # Debug counters
    missing_bpa_sample_id_count = 0
    missing_sample_count = 0
    existing_experiment_count = 0
    missing_required_fields_count = 0
    
    for package_id, experiment_data in experiments_data.items():
        # Check if experiment already exists
        existing = db.query(Experiment).filter(Experiment.bpa_package_id == package_id).first()
        if existing:
            existing_experiment_count += 1
            skipped_experiments_count += 1
            continue
        
        # Get sample reference from experiment data
        bpa_sample_id = experiment_data.get("bpa_sample_id", None)
        if not bpa_sample_id:
            missing_bpa_sample_id_count += 1
            skipped_experiments_count += 1
            continue
        
        # Look up the sample by bpa_sample_id
        sample = db.query(Sample).filter(Sample.bpa_sample_id == bpa_sample_id).first()
        if not sample:
            missing_sample_count += 1
            skipped_experiments_count += 1
            continue
        
        # Check for required fields
        if not experiment_data.get("bpa_library_id", None):
            missing_required_fields_count += 1
            skipped_experiments_count += 1
            continue
        
        try:
            # Create new experiment
            experiment_id = uuid.uuid4()
            sample_id = sample.id
            
            experiment = Experiment(
                id=experiment_id,
                sample_id=sample_id,
                bpa_package_id=package_id,
                bpa_json=experiment_data
            )
            db.add(experiment)
            
            # Find a project for this experiment
            project_id = None
            project = db.query(Project).first()  # Get any project for now, ideally we'd have proper association
            if project:
                project_id = project.id
            
            # Create prepared_payload based on the mapping
            prepared_payload = {}
            for ena_key, atol_key in experiment_mapping.items():
                if atol_key in experiment_data:
                    prepared_payload[ena_key] = experiment_data[atol_key]
            
            # Create experiment_submission record
            experiment_submission = ExperimentSubmission(
                id=uuid.uuid4(),
                experiment_id=experiment_id,
                sample_id=sample_id,
                project_id=project_id,
                authority="ENA",
                entity_type_const="experiment",
                prepared_payload=prepared_payload
            )
            db.add(experiment_submission)
            
            # Process runs if they exist in the experiment data
            if "runs" in experiment_data and isinstance(experiment_data["runs"], list):
                for run in experiment_data["runs"]:
                    try:
                        # Create read entity for each run
                        read = Read(
                            id=uuid.uuid4(),
                            experiment_id=experiment_id,
                            file_name=run.get("file_name", None),
                            file_format=run.get("file_format", None),
                            file_submission_date=run.get("file_submission_date", None),
                            file_checksum=run.get("file_checksum", None),
                            optional_file=run.get("optional_file", False),
                            bioplatforms_url=run.get("bioplatforms_url", ""),
                            reads_access_date=run.get("reads_access_date", None),
                            read_number=run.get("read_number", None),
                            lane_number=run.get("lane_number", None),
                            sra_run_accession=run.get("sra_run_accession", None),
                            run_read_count=run.get("run_read_count", None),
                            run_base_count=run.get("run_base_count", None),
                            bpa_resource_id=run.get("bpa_resource_id", None),
                            bpa_json=run
                        )
                        db.add(read)
                        created_reads_count += 1

                        # Create prepared_payload for run based on the mapping
                        run_prepared_payload = {}
                        for ena_key, atol_key in run_mapping.items():
                            if atol_key in run:
                                run_prepared_payload[ena_key] = run[atol_key]
                        
                        # Create read submission record
                        read_submission = ReadSubmission(
                            id=uuid.uuid4(),
                            read_id=read.id,
                            experiment_id=experiment_id,
                            project_id=project_id,
                            authority="ENA",
                            entity_type_const="read",
                            prepared_payload=run_prepared_payload
                        )
                        db.add(read_submission)
                        created_submission_count += 1
                    except Exception as e:
                        print(f"Error creating read for experiment: {experiment_id}, file: {run.get('file_name')}")
                        print(e)
                        skipped_runs_count += 1
                        # Continue with other runs even if one fails
            
            db.commit()
            created_experiments_count += 1
            created_submission_count += 1
            
        except Exception as e:
            print(f"Error creating experiment with package_id: {package_id}, bpa_sample_id: {bpa_sample_id}")
            print(e)
            db.rollback()
            skipped_experiments_count += 1
    
    return {
        "created_count": created_experiments_count,
        "skipped_experiment_count": skipped_experiments_count,
        "skipped_run_count": skipped_runs_count,
        "message": f"Experiment import complete. Created experiments: {created_experiments_count}, Created submission records: {created_submission_count}, Created reads: {created_reads_count}, Skipped: {skipped_runs_count}",
        "debug": {
            "missing_bpa_sample_id": missing_bpa_sample_id_count,
            "missing_sample": missing_sample_count,
            "existing_experiment": existing_experiment_count,
            "missing_required_fields": missing_required_fields_count
        }
    }


@router.get("/submission/{bpa_package_id}", response_model=ExperimentSubmissionSchema)
async def get_experiment_submission_by_package_id(
    bpa_package_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ExperimentSubmissionSchema:
    """
    Get ExperimentSubmission data for a specific bpa_package_id.
    
    This endpoint retrieves the submission experiment data associated with a specific BPA package ID.
    """
    # Find the experiment with the given bpa_package_id
    experiment = db.query(Experiment).filter(Experiment.bpa_package_id == bpa_package_id).first()
    if not experiment:
        raise HTTPException(
            status_code=404,
            detail=f"Experiment with bpa_package_id {bpa_package_id} not found"
        )
    
    # Find the submission record for this experiment
    submission_record = db.query(ExperimentSubmission).filter(
        ExperimentSubmission.experiment_id == experiment.id
    ).first()
    
    if not submission_record:
        raise HTTPException(
            status_code=404,
            detail=f"No submission record found for experiment with bpa_package_id {bpa_package_id}"
        )
    
    return submission_record

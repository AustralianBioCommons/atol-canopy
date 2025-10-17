import json
import uuid
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
from app.models.sample import Sample, SampleSubmission
from app.models.organism import Organism
from app.models.experiment import Experiment
from app.models.user import User
from app.schemas.sample import (
    Sample as SampleSchema,
    SampleCreate,
    SampleSubmission as SampleSubmissionSchema,
    SampleSubmissionCreate,
    SampleSubmissionUpdate,
    SampleUpdate,
    SubmissionStatus as SchemaSubmissionStatus,
)
from app.schemas.bulk_import import BulkSampleImport, BulkImportResponse
from app.schemas.common import SubmissionJsonResponse
import os

router = APIRouter()


@router.get("/", response_model=List[SampleSchema])
def read_samples(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    organism_key: Optional[str] = Query(None, description="Filter by organism key"),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Retrieve samples.
    """
    # All users can read samples
    query = db.query(Sample)
    if organism_key:
        query = query.filter(Sample.organism_key == organism_key)
    
    samples = query.offset(skip).limit(limit).all()
    return samples


@router.post("/", response_model=SampleSchema)
def create_sample(
    *,
    db: Session = Depends(get_db),
    sample_in: SampleCreate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Create new sample.
    """
    # Only users with 'curator' or 'admin' role can create samples
    require_role(current_user, ["curator", "admin"])
    
    sample = Sample(
        organism_key=sample_in.organism_key,
        bpa_sample_id=sample_in.bpa_sample_id,
        bpa_json=sample_in.bpa_json,
    )
    db.add(sample)
    db.commit()
    db.refresh(sample)
    return sample


@router.get("/{sample_id}/prepared-payload", response_model=SubmissionJsonResponse)
def get_sample_prepared_payload(
    *,
    db: Session = Depends(get_db),
    sample_id: UUID,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get prepared_payload for a specific sample.
    """
    sample_submission = db.query(SampleSubmission).filter(SampleSubmission.sample_id == sample_id).first()
    if not sample_submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sample submission data not found",
        )
    return {"submission_json": sample_submission.prepared_payload}


@router.get("/{sample_id}", response_model=SampleSchema)
def read_sample(
    *,
    db: Session = Depends(get_db),
    sample_id: UUID,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get sample by ID.
    """
    # All users can read sample details
    sample = db.query(Sample).filter(Sample.id == sample_id).first()
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found")
    return sample


@router.put("/{sample_id}", response_model=SampleSchema)
def update_sample(
    *,
    db: Session = Depends(get_db),
    sample_id: UUID,
    sample_in: SampleUpdate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Update a sample.
    """
    # Only users with 'curator' or 'admin' role can update samples
    require_role(current_user, ["curator", "admin"])
    
    sample = db.query(Sample).filter(Sample.id == sample_id).first()
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found")
    
    update_data = sample_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(sample, field, value)
    
    db.add(sample)
    db.commit()
    db.refresh(sample)
    return sample


@router.delete("/{sample_id}", response_model=SampleSchema)
def delete_sample(
    *,
    db: Session = Depends(get_db),
    sample_id: UUID,
    current_user: User = Depends(get_current_superuser),
) -> Any:
    """
    Delete a sample.
    """
    # Only superusers can delete samples
    sample = db.query(Sample).filter(Sample.id == sample_id).first()
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found")
    
    db.delete(sample)
    db.commit()
    return sample


# Sample Submission endpoints
@router.get("/submission/", response_model=List[SampleSubmissionSchema])
def read_sample_submissions(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    status: Optional[SchemaSubmissionStatus] = Query(None, description="Filter by submission status"),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Retrieve sample submissions.
    """
    # All users can read sample submissions
    query = db.query(SampleSubmission)
    if status:
        query = query.filter(SampleSubmission.status == status)
    
    submissions = query.offset(skip).limit(limit).all()
    return submissions


@router.post("/submission/", response_model=SampleSubmissionSchema)
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


@router.put("/submission/{submission_id}", response_model=SampleSubmissionSchema)
def update_sample_submission(
    *,
    db: Session = Depends(get_db),
    submission_id: UUID,
    submission_in: SampleSubmissionUpdate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Update a sample submission.
    """
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


# Sample Fetched endpoints have been removed as they are no longer in the schema

@router.post("/bulk-import", response_model=BulkImportResponse)
def bulk_import_samples(
    *,
    db: Session = Depends(get_db),
    samples_data: Dict[str, Dict[str, Any]],  # Accept direct dictionary format from unique_samples.json
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Bulk import samples from a dictionary keyed by bpa_sample_id.
    
    The request body should directly match the format of the JSON file in data/unique_samples.json,
    which is a dictionary keyed by bpa_sample_id without a wrapping 'samples' key.
    """
    # Only users with 'curator' or 'admin' role can import samples
    require_role(current_user, ["curator", "admin"])
    
    # Load the ENA-ATOL mapping file
    ena_atol_map_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "config", "ena-atol-map.json")
    with open(ena_atol_map_path, "r") as f:
        ena_atol_map = json.load(f)
    
    # Get the sample mapping section
    sample_mapping = ena_atol_map.get("sample", {})
    
    created_samples_count = 0
    created_submission_count = 0
    skipped_count = 0
    
    for bpa_sample_id, sample_data in samples_data.items():
        # Check if sample already exists
        existing = db.query(Sample).filter(Sample.bpa_sample_id == bpa_sample_id).first()
        if existing:
            skipped_count += 1
            continue
        
        # Get organism reference from sample data
        organism_key = None
        if "organism_grouping_key" in sample_data:
            organism_key = sample_data["organism_grouping_key"]
            # Look up the organism by grouping key
            organism = db.query(Organism).filter(Organism.grouping_key == organism_key).first()
        else:
            print(f"Organism not found for sample {bpa_sample_id}, Skipping")
            skipped_count += 1
            continue
        if not organism:
            print(f"Organism not found with grouping_key {organism_key}, Skipping")
            skipped_count += 1
            continue
        try:
            # Create new sample
            sample_id = uuid.uuid4()
            sample = Sample(
                id=sample_id,
                organism_key=organism_key,
                bpa_sample_id=bpa_sample_id,
                bpa_json=sample_data
            )
            db.add(sample)
            
            # Create prepared_payload based on the mapping
            prepared_payload = {}
            for ena_key, atol_key in sample_mapping.items():
                if atol_key in sample_data:
                    prepared_payload[ena_key] = sample_data[atol_key]
            
            # Create sample_submission record
            sample_submission = SampleSubmission(
                id=uuid.uuid4(),
                sample_id=sample_id,
                authority="ENA",
                entity_type_const="sample",
                prepared_payload=prepared_payload
            )
            db.add(sample_submission)
            
            db.commit()
            created_samples_count += 1
            created_submission_count += 1
            
        except Exception as e:
            print(f"Error creating sample with bpa_sample_id: {bpa_sample_id}")
            print(e)
            db.rollback()
            skipped_count += 1
    
    return {
        "created_count": created_samples_count,
        "skipped_count": skipped_count,
        "message": f"Sample import complete. Created samples: {created_samples_count}, "
                  f"Created submission records: {created_submission_count}, Skipped: {skipped_count}"
    }


@router.get("/submission/by-experiment/{bpa_package_id}", response_model=List[SampleSubmissionSchema])
async def get_sample_submission_by_experiment_package_id(
    bpa_package_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[SampleSubmissionSchema]:
    """
    Get SampleSubmission data for a specific experiment.bpa_package_id.
    
    This endpoint retrieves all submission sample data associated with a specific experiment BPA package ID.
    """
    # Find the experiment with the given bpa_package_id
    experiment = db.query(Experiment).filter(Experiment.bpa_package_id == bpa_package_id).first()
    if not experiment:
        raise HTTPException(
            status_code=404,
            detail=f"Experiment with bpa_package_id {bpa_package_id} not found"
        )
    
    # Get the sample_id from the experiment
    if not experiment.sample_id:
        raise HTTPException(
            status_code=404,
            detail=f"Experiment with bpa_package_id {bpa_package_id} has no associated sample"
        )
    
    # Find the submission records for this sample
    submission_records = db.query(SampleSubmission).filter(
        SampleSubmission.sample_id == experiment.sample_id
    ).all()
    
    if not submission_records:
        raise HTTPException(
            status_code=404,
            detail=f"No submission sample records found for experiment with bpa_package_id {bpa_package_id}"
        )
    
    return submission_records

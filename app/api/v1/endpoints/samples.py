import json
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

    sample_data = sample_in.dict(exclude_unset=True)
    sample_id = uuid.uuid4()
    sample = Sample(
        id=sample_id,
        organism_key=sample_in.organism_key,
        bpa_sample_id=sample_in.bpa_sample_id,
        bpa_json=sample_data,
    )
    db.add(sample)

     # Load the ENA-ATOL mapping file
    ena_atol_map_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "config", "ena-atol-map.json")
    with open(ena_atol_map_path, "r") as f:
        ena_atol_map = json.load(f)
    # Generate ENA-mapped data for submission to ENA
    prepared_payload = {}
    for ena_key, atol_key in ena_atol_map["sample"].items():
        if atol_key in sample_data:
            prepared_payload[ena_key] = sample_data[atol_key]

    sample_submission = SampleSubmission(
        sample_id=sample_id,
        authority=sample_in.authority,
        entity_type_const="sample",
        prepared_payload=prepared_payload,
        status="draft",
    )
    db.add(sample_submission)
    db.commit()
    db.refresh(sample)
    db.refresh(sample_submission)
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
    # Admin, curator, broker and genome_launcher can get submission data
    require_role(current_user, ["admin", "curator", "broker", "genome_launcher"])
    sample_submission = db.query(SampleSubmission).filter(SampleSubmission.sample_id == sample_id).first()
    if not sample_submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sample submission data not found",
        )
    return {"prepared_payload": getattr(sample_submission, "prepared_payload")}


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
    
    try:
        sample = db.query(Sample).filter(Sample.id == sample_id).first()
        if not sample:
            raise HTTPException(status_code=404, detail="Sample not found")

        sample_data = sample_in.dict(exclude_unset=True)
        # Load the ENA-ATOL mapping file
        ena_atol_map_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "config", "ena-atol-map.json")
        with open(ena_atol_map_path, "r") as f:
            ena_atol_map = json.load(f)
        # Generate ENA-mapped data for submission to ENA
        prepared_payload = {}
        for ena_key, atol_key in ena_atol_map["sample"].items():
            if atol_key in sample_data:
                prepared_payload[ena_key] = sample_data[atol_key]
        sample_submission = db.query(SampleSubmission).filter(SampleSubmission.sample_id == sample_id).order_by(SampleSubmission.updated_at.desc()).first()
        new_sample_submission = None
        latest_sample_submission = {}
        if not sample_submission:
            new_sample_submission = SampleSubmission(
                    sample_id=sample_id,
                    authority=sample_submission.authority,
                    entity_type_const="sample",
                    prepared_payload=prepared_payload,
                    status="draft",
                )
            db.add(new_sample_submission)
        else:
            latest_sample_submission = sample_submission
            
            if latest_sample_submission.status == "submitting":
                raise HTTPException(status_code=404, detail=f"Sample with id: {sample_id} is currently being submitted to ENA and could not be updated. Please try again later.")
            elif latest_sample_submission.status == "rejected" or sample_submission.status == "replaced":
                # leave the old record for logs and create a new record
                # retain accessions if they exist (accessions may not exist if status is 'rejected' and the sample has not successfully been submitted in the past)
                new_sample_submission = SampleSubmission(
                    sample_id=sample_id,
                    authority=sample_submission.authority,
                    entity_type_const="sample",
                    prepared_payload=prepared_payload,
                    response_payload=None,
                    accession=sample_submission.accession,
                    biosample_accession=sample_submission.biosample_accession,
                    status="draft",
                )
                db.add(new_sample_submission)
                
            elif latest_sample_submission.status == "accepted":
                # change old record's status to "replaced" and create a new record
                # retain accessions
                setattr(latest_sample_submission, "status", "replaced")
                db.add(latest_sample_submission)
                new_sample_submission = SampleSubmission(
                    sample_id=sample_id,
                    authority=sample_submission.authority,
                    entity_type_const="sample",
                    prepared_payload=prepared_payload,
                    response_payload=None,
                    accession=sample_submission.accession,
                    biosample_accession=sample_submission.biosample_accession,
                    status="draft",
                )
                db.add(new_sample_submission)
            elif latest_sample_submission.status == "draft" or latest_sample_submission.status == "ready":
                # update the existing record, since it has not yet been submitted to ENA (set status = 'draft')
                setattr(latest_sample_submission, "prepared_payload", prepared_payload)
                setattr(latest_sample_submission, "status", "draft")
                db.add(latest_sample_submission)
                # update the sample_submission object
                
        # initiate new bpa_json object to the previous bpa_json object
        new_bpa_json = sample.bpa_json
        update_data = sample_data
        setattr(sample, "organism_key", sample_in.organism_key)
        setattr(sample, "bpa_sample_id", sample_in.bpa_sample_id)
        for field, value in update_data.items():
            new_bpa_json[field] = value
        sample.bpa_json = new_bpa_json
        flag_modified(sample, "bpa_json")
        db.add(sample)
        db.commit()
        db.refresh(sample)
        return sample
    except Exception as e:
        print(f"Error updating sample with sample_id: {sample_id}")
        print(e)
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update sample")


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
    require_role(current_user, ["superuser", "admin"])
    sample = db.query(Sample).filter(Sample.id == sample_id).first()
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found")
    
    db.delete(sample)
    db.commit()
    return sample

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

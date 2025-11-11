import uuid
from typing import Any, List, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import (
    get_current_active_user,
    get_current_superuser,
    get_db,
    require_role,
)
from app.models.organism import Organism
from app.models.sample import Sample, SampleSubmission
from app.models.experiment import Experiment, ExperimentSubmission
from app.models.read import Read, ReadSubmission
from app.models.user import User
from app.schemas.organism import (
    Organism as OrganismSchema,
    OrganismCreate,
    OrganismUpdate,
)
from app.schemas.bulk_import import BulkOrganismImport, BulkImportResponse
from app.schemas.aggregate import OrganismSubmissionJsonResponse, SampleSubmissionJson, ExperimentSubmissionJson, ReadSubmissionJson

router = APIRouter()

def _sa_obj_to_dict(obj):
    """Serialize all SQLAlchemy column fields for a model instance."""
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


@router.get("/", response_model=List[OrganismSchema])
def read_organisms(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Retrieve organisms.
    """
    # All users can read organisms
    organisms = db.query(Organism).offset(skip).limit(limit).all()
    return organisms


@router.get("/{grouping_key}/experiments")
def get_experiments_for_organism(
    *,
    db: Session = Depends(get_db),
    grouping_key: str,
    includeReads: bool = Query(False, description="Include reads for each experiment"),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Return all experiments for the organism, and optionally all reads for each experiment when includeReads is true.
    """
    # Admin, curator, broker and genome_launcher can get expanded organism data
    require_role(current_user, ["admin", "curator", "broker", "genome_launcher"])

    organism = db.query(Organism).filter(Organism.grouping_key == grouping_key).first()
    if not organism:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Organism with grouping key '{grouping_key}' not found")

    # Find all samples for this organism
    samples = db.query(Sample.id).filter(Sample.organism_key == grouping_key).all()
    sample_ids = [sid for (sid,) in samples]

    # Load experiments
    experiments = []
    if sample_ids:
        experiments = db.query(Experiment).filter(Experiment.sample_id.in_(sample_ids)).all()

    # Build response
    if not includeReads:
        # Return all experiment fields
        exp_list = [_sa_obj_to_dict(e) for e in experiments]
        return {"grouping_key": grouping_key, "experiments": exp_list}

    # includeReads = True
    exp_ids = [e.id for e in experiments]
    reads_by_exp: Dict[str, List[Dict[str, Any]]] = {}
    if exp_ids:
        reads = db.query(Read).filter(Read.experiment_id.in_(exp_ids)).all()
        for r in reads:
            key = str(r.experiment_id) if r.experiment_id else "null"
            if key not in reads_by_exp:
                reads_by_exp[key] = []
            reads_by_exp[key].append(_sa_obj_to_dict(r))

    exp_with_reads = []
    for e in experiments:
        item = _sa_obj_to_dict(e)
        item["reads"] = reads_by_exp.get(str(e.id), [])
        exp_with_reads.append(item)

    return {
        "grouping_key": grouping_key,
        "experiments": exp_with_reads,
    }


@router.get("/submissions/{grouping_key}", response_model=OrganismSubmissionJsonResponse)
def get_organism_submission_json(
    *,
    db: Session = Depends(get_db),
    grouping_key: str,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get all submission_json data for samples, experiments, and reads related to a specific grouping_key.
    """
    # Admin, curator, broker and genome_launcher can get submission_json data
    require_role(current_user, ["admin", "curator", "broker", "genome_launcher"])
    
    # Find the organism by grouping key
    organism = db.query(Organism).filter(Organism.grouping_key == grouping_key).first()
    if not organism:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organism with grouping key '{grouping_key}' not found",
        )
    
    # Initialize response object
    response = OrganismSubmissionJsonResponse(
        grouping_key=organism.grouping_key,
        tax_id=organism.tax_id,
        scientific_name=organism.scientific_name,
        common_name=organism.common_name,
        common_name_source=organism.common_name_source,
        samples=[],
        experiments=[],
        reads=[]
    )
    
    # Get samples for this organism
    samples = db.query(Sample).filter(Sample.organism_key == organism.grouping_key).all()
    sample_ids = [sample.id for sample in samples]
    
    # Get sample submission data
    if sample_ids:
        sample_submission_records = db.query(SampleSubmission).filter(SampleSubmission.sample_id.in_(sample_ids)).all()
        response.samples = sample_submission_records
        """
        for record in sample_submission_records:
            # Find the corresponding sample to get the bpa_sample_id
            sample = next((s for s in samples if s.id == record.sample_id), None)
            bpa_sample_id = sample.bpa_sample_id if sample else None
            
            response.samples.append(SampleSubmissionJson(
                sample_id=record.sample_id,
                bpa_sample_id=bpa_sample_id,
                prepared_payload=record.prepared_payload,
                status=record.status
            ))
        """
    
    # Get experiments for these samples
    if sample_ids:
        experiments = db.query(Experiment).filter(Experiment.sample_id.in_(sample_ids)).all()
        experiment_ids = [experiment.id for experiment in experiments]
        
        # Get experiment submission data
        if experiment_ids:
            experiment_submission_records = db.query(ExperimentSubmission).filter(ExperimentSubmission.experiment_id.in_(experiment_ids)).all()
            response.experiments = experiment_submission_records
            for record in experiment_submission_records:
                # Find the corresponding experiment to get the bpa_package_id
                # experiment = next((e for e in experiments if e.id == record.experiment_id), None)
                # bpa_package_id = experiment.bpa_package_id if experiment else None
                """
                response.experiments.append(ExperimentSubmissionJson(
                    experiment_id=record.experiment_id,
                    bpa_package_id=bpa_package_id,
                    prepared_payload=record.prepared_payload,
                    status=record.status
                ))
                """
                reads = db.query(Read).filter(Read.experiment_id.in_(experiment_ids)).all()
                read_ids = [read.id for read in reads]
                print("reads: ",read_ids)
                
                # Get read submission data
                if read_ids:
                    read_submission_records = db.query(ReadSubmission).filter(ReadSubmission.read_id.in_(read_ids)).all()
                    response.reads = read_submission_records

        # TO DO append reads    
    return response


@router.post("/", response_model=OrganismSchema)
def create_organism(
    *,
    db: Session = Depends(get_db),
    organism_in: OrganismCreate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Create new organism.
    """
    # Only users with 'curator' or 'admin' role can create organisms
    require_role(current_user, ["curator", "admin"])
    common_name = organism_in.common_name
    common_name_source = organism_in.common_name_source
    if common_name and not common_name_source:
        common_name_source = "BPA"
    organism = Organism(
        grouping_key=organism_in.grouping_key,
        tax_id=organism_in.tax_id,
        scientific_name=organism_in.scientific_name,
        common_name=common_name,
        common_name_source=common_name_source,
        taxonomy_lineage_json=organism_in.taxonomy_lineage_json,
        bpa_json=organism_in.dict(exclude_unset=True),
    )
    db.add(organism)
    db.commit()
    db.refresh(organism)
    return organism


@router.get("/{grouping_key}", response_model=OrganismSchema)
def read_organism(
    *,
    db: Session = Depends(get_db),
    grouping_key: str,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get organism by grouping_key.
    """
    # All users can read organism details
    organism = db.query(Organism).filter(Organism.grouping_key == grouping_key).first()
    if not organism:
        raise HTTPException(status_code=404, detail="Organism not found")
    return organism


@router.patch("/{grouping_key}", response_model=OrganismSchema)
def update_organism(
    *,
    db: Session = Depends(get_db),
    grouping_key: str,
    organism_in: OrganismUpdate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Update an organism.
    """
    # Only users with 'curator' or 'admin' role can update organisms
    require_role(current_user, ["curator", "admin"])
    
    organism = db.query(Organism).filter(Organism.grouping_key == grouping_key).first()
    if not organism:
        raise HTTPException(status_code=404, detail="Organism not found")
    new_bpa_json = organism.bpa_json
    update_data = organism_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(organism, field, value)
        if field == "common_name_source":
            continue
        setattr(new_bpa_json, field, value)
    
    setattr(organism, "bpa_json", new_bpa_json)
    db.add(organism)
    db.commit()
    db.refresh(organism)
    return organism


@router.delete("/{grouping_key}", response_model=OrganismSchema)
def delete_organism(
    *,
    db: Session = Depends(get_db),
    grouping_key: str,
    current_user: User = Depends(get_current_superuser),
) -> Any:
    """
    Delete an organism.
    """
    # Only users with 'superuser' or 'admin' role can delete organisms
    require_role(current_user, ["admin", "superuser"])

    print("deleting organism with grouping key: ", grouping_key)
    
    organism = db.query(Organism).filter(Organism.grouping_key == grouping_key).first()
    if not organism:
        raise HTTPException(status_code=404, detail="Organism not found")
    
    db.delete(organism)
    db.commit()
    return organism


@router.post("/bulk-import", response_model=BulkImportResponse)
def bulk_import_organisms(
    *,
    db: Session = Depends(get_db),
    organisms_data: Dict[str, Dict[str, Any]],  # Accept direct dictionary format from unique_organisms.json
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Bulk import organisms from a dictionary keyed by organism_grouping_key.
    
    The request body should directly match the format of the JSON file in data/unique_organisms.json,
    which is a dictionary keyed by organism_grouping_key without a wrapping 'organisms' key.
    """
    # Only users with 'curator' or 'admin' role can import organisms
    require_role(current_user, ["curator", "admin"])
    
    created_count = 0
    skipped_count = 0
    
    for organism_grouping_key, organism_data in organisms_data.items():
        # Extract tax_id from the organism data
        if "taxon_id" in organism_data:
            tax_id = organism_data["taxon_id"]
        else:
            print(f"Missing taxon_id for organism: {organism_data}")
            skipped_count += 1
            continue
        
        if "organism_grouping_key" not in organism_data:
            print(f"Missing organism_grouping_key for organism: {organism_data}")
            skipped_count += 1
            continue
        
        # Check if organism already exists by grouping key
        existing = db.query(Organism).filter(Organism.grouping_key == organism_grouping_key).first()
        if existing:
            skipped_count += 1
            continue
        
        # Create new organism
        scientific_name = organism_data.get("scientific_name")
        if not scientific_name:
            skipped_count += 1
            continue
        
        try:
            common_name = organism_data.get("common_name", None)
            common_name_source = organism_data.get("common_name_source", "BPA") if common_name is not None else None
            # Create new organism
            organism = Organism(
                grouping_key=organism_grouping_key,
                tax_id=tax_id,
                common_name=common_name,
                common_name_source=common_name_source,
                scientific_name=scientific_name,
                bpa_json=organism_data
            )
            db.add(organism)
            db.commit()
            created_count += 1
        except Exception as e:
            db.rollback()
            skipped_count += 1
    
    return {
        "created_count": created_count,
        "skipped_count": skipped_count,
        "message": f"Organism import complete. Created: {created_count}, Skipped: {skipped_count}"
    }

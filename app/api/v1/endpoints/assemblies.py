from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import (
    get_current_active_user,
    get_current_superuser,
    get_db,
    require_role,
)
from app.models.assembly import Assembly, AssemblySubmission
from app.models.organism import Organism
from app.models.sample import Sample
from app.models.experiment import Experiment
from app.models.read import Read
from app.schemas.common import SubmissionStatus
from app.models.user import User
from app.services.organism_service import organism_service
from app.schemas.assembly import (
    Assembly as AssemblySchema,
    AssemblyCreate,
    AssemblySubmission as AssemblySubmissionSchema,
    AssemblySubmissionCreate,
    AssemblySubmissionUpdate,
    AssemblyUpdate,
    SubmissionStatus as SchemaSubmissionStatus,
)

router = APIRouter()

"""
@router.get("/", response_model=List[AssemblySchema])
def read_assemblies(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    organism_id: Optional[UUID] = Query(None, description="Filter by organism ID"),
    sample_id: Optional[UUID] = Query(None, description="Filter by sample ID"),
    experiment_id: Optional[UUID] = Query(None, description="Filter by experiment ID"),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    Retrieve assemblies.
    # All users can read assemblies
    query = db.query(Assembly)
    if organism_id:
        query = query.filter(Assembly.organism_id == organism_id)
    if sample_id:
        query = query.filter(Assembly.sample_id == sample_id)
    if experiment_id:
        query = query.filter(Assembly.experiment_id == experiment_id)
    
    assemblies = query.offset(skip).limit(limit).all()
    return assemblies
"""

@router.get("/pipeline-inputs")
def get_pipeline_inputs(
    *,
    db: Session = Depends(get_db),
    organism_grouping_key: str = Query(None, description="Organism grouping key to filter by"),
    tax_id: str = Query(None, description="Organism tax ID to filter by"),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get pipeline inputs for an organism by organism_grouping_key.
    
    Returns a list of objects with scientific_name and files mapping for each organism.
    Files mapping contains read file names as keys and their bioplatforms_urls as values.
    """
    print(f"Organism grouping key: {organism_grouping_key}")
    
    # Check if organism_grouping_key was provided
    if organism_grouping_key is None:
        raise HTTPException(status_code=422, detail="organism_grouping_key query parameter is required")
    if db is None:
        raise HTTPException(status_code=422, detail="database session is required")
    # Get the organism by organism_grouping_key
    organism = organism_service.get_by_grouping_key(db, organism_grouping_key)
    if not organism:
        print(f"Organism with grouping key '{organism_grouping_key}' not found")
        raise HTTPException(status_code=404, detail=f"Organism with grouping key '{organism_grouping_key}' not found")
    
    # Get all samples for this organism
    samples = db.query(Sample).filter(Sample.organism_key == organism.grouping_key).all()
    if not samples:
        print(f"No samples found for organism with grouping key '{organism_grouping_key}'")
        return [{
            "scientific_name": organism.scientific_name,
            "tax_id": organism.tax_id,
            "files": {}
        }]
    
    # Get all experiments and reads for these samples
    result = []
    files_dict = {}
    
    # Collect all reads for this organism through the sample->experiment->read relationship
    for sample in samples:
        print(f"Sample {sample.id} found for organism with grouping key '{organism_grouping_key}'")
        # Get experiments for this sample
        experiments = db.query(Experiment).filter(Experiment.sample_id == sample.id).all()
        
        for experiment in experiments:
            print(f"Experiment {experiment.id} found for sample {sample.id}")
            # Get reads for this experiment
            reads = db.query(Read).filter(Read.experiment_id == experiment.id).all()
            
            for read in reads:
                print(f"Read {read.id} found for experiment {experiment.id}")
                if read.file_name and read.bioplatforms_url:
                    files_dict[read.file_name] = read.bioplatforms_url
    
    # Create the result object
    result.append({
        "scientific_name": organism.scientific_name,
        "tax_id": organism.tax_id,       
        "files": files_dict
    })
    
    return result


@router.get("/pipeline-inputs-by-tax-id")
def get_pipeline_inputs_by_tax_id(
    *,
    db: Session = Depends(get_db),
    tax_id: str = Query(None, description="Organism tax ID to filter by"),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get pipeline inputs for organisms by tax_id.
    
    Returns a nested structure with tax_id as the top level key, organism_grouping_key as the second level key,
    and scientific_name and files mapping for each organism.
    Files mapping contains read file names as keys and their bioplatforms_urls as values.
    """
    print(f"Tax ID: {tax_id}")
    
    # Check if tax_id was provided
    if tax_id is None:
        raise HTTPException(status_code=422, detail="tax_id query parameter is required")
    
    # Get all organisms with this tax_id
    organisms = organism_service.get_multi_with_filters(db, tax_id=tax_id)
    if not organisms:
        print(f"No organisms found with tax ID '{tax_id}'")
        return {tax_id: {}}
    
    # Initialize result structure
    result = {tax_id: {}}
    
    # Process each organism
    for organism in organisms:
        print(f"Found organism {organism.grouping_key} with tax ID '{tax_id}'")
        organism_key = organism.grouping_key
        result[tax_id][organism_key] = {
            "scientific_name": organism.scientific_name,
            "files": {}
        }
        
        # Get all samples for this organism
        samples = db.query(Sample).filter(Sample.organism_key == organism.grouping_key).all()
        if not samples:
            print(f"No samples found for organism with ID {organism.grouping_key}")
            continue
        
        # Collect all reads for this organism through the sample->experiment->read relationship
        for sample in samples:
            print(f"Sample {sample.id} found for organism {organism.grouping_key}")
            # Get experiments for this sample
            experiments = db.query(Experiment).filter(Experiment.sample_id == sample.id).all()
            
            for experiment in experiments:
                print(f"Experiment {experiment.id} found for sample {sample.id}")
                # Get reads for this experiment
                reads = db.query(Read).filter(Read.experiment_id == experiment.id).all()
                
                for read in reads:
                    print(f"Read {read.id} found for experiment {experiment.id}")
                    if read.file_name and read.bioplatforms_url:
                        result[tax_id][organism_key]["files"][read.file_name] = read.bioplatforms_url
    
    return result

"""
@router.post("/", response_model=AssemblySchema)
def create_assembly(
    *,
    db: Session = Depends(get_db),
    assembly_in: AssemblyCreate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    # Create new assembly.
    # Only users with 'curator' or 'admin' role can create assemblies
    require_role(current_user, ["curator", "admin"])
    
    assembly = Assembly(
        organism_id=assembly_in.organism_id,
        sample_id=assembly_in.sample_id,
        experiment_id=assembly_in.experiment_id,
        assembly_accession=assembly_in.assembly_accession,
        source_json=assembly_in.source_json,
        internal_notes=assembly_in.internal_notes,
    )
    db.add(assembly)
    db.commit()
    db.refresh(assembly)
    return assembly


@router.get("/{assembly_id}", response_model=AssemblySchema)
def read_assembly(
    *,
    db: Session = Depends(get_db),
    assembly_id: UUID,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    # Get assembly by ID.
    # All users can read assembly details
    assembly = db.query(Assembly).filter(Assembly.id == assembly_id).first()
    if not assembly:
        raise HTTPException(status_code=404, detail="Assembly not found")
    return assembly


@router.put("/{assembly_id}", response_model=AssemblySchema)
def update_assembly(
    *,
    db: Session = Depends(get_db),
    assembly_id: UUID,
    assembly_in: AssemblyUpdate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    # Update an assembly.
    # Only users with 'curator' or 'admin' role can update assemblies
    require_role(current_user, ["curator", "admin"])
    
    assembly = db.query(Assembly).filter(Assembly.id == assembly_id).first()
    if not assembly:
        raise HTTPException(status_code=404, detail="Assembly not found")
    
    update_data = assembly_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(assembly, field, value)
    
    db.add(assembly)
    db.commit()
    db.refresh(assembly)
    return assembly


@router.delete("/{assembly_id}", response_model=AssemblySchema)
def delete_assembly(
    *,
    db: Session = Depends(get_db),
    assembly_id: UUID,
    current_user: User = Depends(get_current_superuser),
) -> Any:
    # Delete an assembly.
    # Only superusers can delete assemblies
    assembly = db.query(Assembly).filter(Assembly.id == assembly_id).first()
    if not assembly:
        raise HTTPException(status_code=404, detail="Assembly not found")
    
    db.delete(assembly)
    db.commit()
    return assembly


# Assembly Submission endpoints
@router.get("/submission/", response_model=List[AssemblySubmissionSchema])
def read_assembly_submissions(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    status: Optional[SchemaSubmissionStatus] = Query(None, description="Filter by submission status"),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    # Retrieve assembly submissions.
    # All users can read assembly submissions
    query = db.query(AssemblySubmission)
    if status:
        query = query.filter(AssemblySubmission.status == status)
    
    submissions = query.offset(skip).limit(limit).all()
    return submissions


@router.post("/submission/", response_model=AssemblySubmissionSchema)
def create_assembly_submission(
    *,
    db: Session = Depends(get_db),
    submission_in: AssemblySubmissionCreate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    # Create new assembly submission.
    # Only users with 'curator' or 'admin' role can create assembly submissions
    require_role(current_user, ["curator", "admin"])
    
    submission = AssemblySubmission(
        assembly_id=submission_in.assembly_id,
        organism_id=submission_in.organism_id,
        sample_id=submission_in.sample_id,
        experiment_id=submission_in.experiment_id,
        assembly_accession=submission_in.assembly_accession,
        submission_json=submission_in.submission_json,
        internal_json=submission_in.internal_json,
        status=submission_in.status,
        submission_at=submission_in.submission_at,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return submission


@router.put("/submission/{submission_id}", response_model=AssemblySubmissionSchema)
def update_assembly_submission(
    *,
    db: Session = Depends(get_db),
    submission_id: UUID,
    submission_in: AssemblySubmissionUpdate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    # Update an assembly submission.
    # Only users with 'curator' or 'admin' role can update assembly submissions
    require_role(current_user, ["curator", "admin"])
    
    submission = db.query(AssemblySubmission).filter(AssemblySubmission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Assembly submission not found")
    
    update_data = submission_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(submission, field, value)
    
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return submission

"""
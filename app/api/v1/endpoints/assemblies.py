from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_active_user, get_db
from app.core.pagination import Pagination, apply_pagination, pagination_params
from app.core.policy import policy
from app.models.assembly import Assembly, AssemblyFile, AssemblyRun, AssemblySubmission
from app.models.experiment import Experiment
from app.models.organism import Organism
from app.models.read import Read
from app.models.sample import Sample
from app.models.user import User
from app.schemas.assembly import (
    Assembly as AssemblySchema,
)
from app.schemas.assembly import (
    AssemblyCreate,
    AssemblyCreateFromExperiments,
    AssemblyFileCreate,
    AssemblyFileUpdate,
    AssemblyIntent,
    AssemblySubmissionCreate,
    AssemblySubmissionUpdate,
    AssemblyUpdate,
)
from app.schemas.assembly import (
    AssemblyFile as AssemblyFileSchema,
)
from app.schemas.assembly import (
    AssemblySubmission as AssemblySubmissionSchema,
)
from app.schemas.common import SubmissionStatus
from app.services.assembly_helper import determine_assembly_data_types, generate_assembly_manifest
from app.services.assembly_service import (
    assembly_file_service,
    assembly_service,
    assembly_submission_service,
)
from app.services.organism_service import organism_service

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
        raise HTTPException(
            status_code=422, detail="organism_grouping_key query parameter is required"
        )
    if db is None:
        raise HTTPException(status_code=422, detail="database session is required")
    # Get the organism by organism_grouping_key
    organism = organism_service.get_by_grouping_key(db, organism_grouping_key)
    if not organism:
        print(f"Organism with grouping key '{organism_grouping_key}' not found")
        raise HTTPException(
            status_code=404,
            detail=f"Organism with grouping key '{organism_grouping_key}' not found",
        )

    # Get all samples for this organism
    samples = db.query(Sample).filter(Sample.organism_key == organism.grouping_key).all()
    if not samples:
        print(f"No samples found for organism with grouping key '{organism_grouping_key}'")
        return [
            {"scientific_name": organism.scientific_name, "tax_id": organism.tax_id, "files": {}}
        ]

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

            if reads is None:
                continue

            for read in reads:
                print(f"Read {read.id} found for experiment {experiment.id}")
                if read.file_name and read.bioplatforms_url:
                    files_dict[read.file_name] = read.bioplatforms_url

    # Create the result object
    result.append(
        {
            "scientific_name": organism.scientific_name,
            "tax_id": organism.tax_id,
            "files": files_dict,
        }
    )

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
        result[tax_id][organism_key] = {"scientific_name": organism.scientific_name, "files": {}}

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
                        result[tax_id][organism_key]["files"][read.file_name] = (
                            read.bioplatforms_url
                        )

    return result


def _get_manifest_inputs_by_tax_id(db: Session, tax_id: int, sample_id: UUID):
    organism = db.query(Organism).filter(Organism.tax_id == tax_id).first()
    if not organism:
        raise HTTPException(status_code=404, detail=f"Organism with tax_id {tax_id} not found")

    sample = db.query(Sample).filter(Sample.id == sample_id).first()
    # if not sample or sample.organism_key != organism.grouping_key:
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found for this organism")

    experiments = db.query(Experiment).filter(Experiment.sample_id == sample_id).all()
    if not experiments:
        raise HTTPException(
            status_code=404,
            detail=f"No experiments found for organism {organism.grouping_key} and sample {sample_id} (tax_id: {tax_id})",
        )

    experiment_ids = [exp.id for exp in experiments]
    reads = db.query(Read).filter(Read.experiment_id.in_(experiment_ids)).all()
    if not reads:
        raise HTTPException(
            status_code=404,
            detail=f"No reads found for organism {organism.grouping_key} (tax_id: {tax_id})",
        )

    return organism, reads, experiments


def _get_optimal_sample_id_for_tax_id(db: Session, tax_id: int) -> UUID | None:
    # TODO: Implement specimen/long-read selection logic.
    # Placeholder for now; return None to indicate no automatic selection.
    _ = db, tax_id
    return None


@router.get("/manifest/{tax_id}")
def get_assembly_manifest(
    *,
    db: Session = Depends(get_db),
    tax_id: int,
    sample_id: UUID = Query(..., description="Sample ID for the manifest"),
    version: Optional[int] = Query(None, description="Reserved manifest version to retrieve"),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Retrieve the latest reserved assembly manifest YAML for an organism by tax_id.

    Returns YAML manifest with:
    - scientific_name and taxon_id from organism
    - reads grouped by platform (PACBIO_SMRT, Hi-C)
    - PACBIO_SMRT: Only files ending in .ccs.bam or hifi_reads.bam
    - Hi-C: Includes read_number and lane_number

    Returns:
        YAML string with manifest data
    """
    from fastapi.responses import Response

    organism, reads, experiments = _get_manifest_inputs_by_tax_id(db, tax_id, sample_id)

    run_query = (
        db.query(AssemblyRun)
        .filter(
            AssemblyRun.organism_key == organism.grouping_key,
            AssemblyRun.sample_id == sample_id,
        )
        .order_by(AssemblyRun.created_at.desc())
    )
    if version is not None:
        run_query = run_query.filter(AssemblyRun.version == version)
    assembly_run = run_query.first()
    if not assembly_run:
        raise HTTPException(status_code=404, detail="No reserved assembly manifest found")

    yaml_content = generate_assembly_manifest(
        organism, reads, experiments, assembly_run.tol_id, assembly_run.version
    )

    # Return as YAML response
    return Response(content=yaml_content, media_type="application/x-yaml")


@router.post("/intent/{tax_id}")
@policy("assemblies:write")
def create_assembly_intent(
    *,
    db: Session = Depends(get_db),
    tax_id: int,
    intent_in: AssemblyIntent,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Reserve the next assembly version and return a manifest.
    """
    from fastapi.responses import Response

    organism, reads, experiments = _get_manifest_inputs_by_tax_id(db, tax_id, intent_in.sample_id)
    data_types = determine_assembly_data_types(experiments)
    next_version = assembly_service.get_next_version(
        db,
        organism_key=organism.grouping_key,
        sample_id=intent_in.sample_id,
        data_types=data_types,
    )

    run = AssemblyRun(
        organism_key=organism.grouping_key,
        sample_id=intent_in.sample_id,
        data_types=data_types,
        version=next_version,
        tol_id=intent_in.tol_id,
        status="reserved",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    yaml_content = generate_assembly_manifest(organism, reads, experiments, run.tol_id, run.version)
    return Response(content=yaml_content, media_type="application/x-yaml")


@router.get("/optimal-sample/{tax_id}")
def get_optimal_sample_id(
    *,
    db: Session = Depends(get_db),
    tax_id: int,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    sample_id = _get_optimal_sample_id_for_tax_id(db, tax_id)
    return {"sample_id": str(sample_id) if sample_id else None}


@router.post("/from-experiments/{tax_id}", response_model=AssemblySchema)
@policy("assemblies:write")
def create_assembly_from_experiments(
    *,
    db: Session = Depends(get_db),
    tax_id: int,
    assembly_in: AssemblyCreateFromExperiments,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Create assembly based on all experiments for an organism (by tax_id).

    Automatically determines data_types by analyzing experiment platforms:
    - PACBIO_SMRT: platform == "PACBIO_SMRT"
    - OXFORD_NANOPORE: platform == "OXFORD_NANOPORE"
    - Hi-C: platform == "ILLUMINA" AND library_strategy == "Hi-C"

    The organism_key is automatically determined from tax_id.
    The data_types field is auto-detected but can be overridden.
    """
    try:
        assembly, platform_info = assembly_service.create_from_experiments(
            db, tax_id=tax_id, assembly_in=assembly_in
        )
        return assembly
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/", response_model=AssemblySchema)
@policy("assemblies:write")
def create_assembly(
    *,
    db: Session = Depends(get_db),
    assembly_in: AssemblyCreate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    assembly = assembly_service.create(db, obj_in=assembly_in)
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
@policy("assemblies:write")
def update_assembly(
    *,
    db: Session = Depends(get_db),
    assembly_id: UUID,
    assembly_in: AssemblyUpdate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
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
@policy("assemblies:delete")
def delete_assembly(
    *,
    db: Session = Depends(get_db),
    assembly_id: UUID,
    current_user: User = Depends(get_current_active_user),
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
    pagination: Pagination = Depends(pagination_params),
    status: Optional[SubmissionStatus] = Query(None, description="Filter by submission status"),
    assembly_id: Optional[UUID] = Query(None, description="Filter by assembly ID"),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Retrieve assembly submissions."""
    if assembly_id:
        submissions = assembly_submission_service.get_by_assembly_id(db, assembly_id=assembly_id)
    else:
        query = db.query(AssemblySubmission)
        if status:
            query = query.filter(AssemblySubmission.status == status.value)
        submissions = apply_pagination(query, pagination).all()

    return submissions


@router.post("/submission/", response_model=AssemblySubmissionSchema)
@policy("assemblies:write")
def create_assembly_submission(
    *,
    db: Session = Depends(get_db),
    submission_in: AssemblySubmissionCreate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Create new assembly submission."""

    # Verify assembly exists
    assembly = assembly_service.get(db, id=submission_in.assembly_id)
    if not assembly:
        raise HTTPException(status_code=404, detail="Assembly not found")

    submission = assembly_submission_service.create(db, obj_in=submission_in)
    return submission


@router.put("/submission/{submission_id}", response_model=AssemblySubmissionSchema)
@policy("assemblies:write")
def update_assembly_submission(
    *,
    db: Session = Depends(get_db),
    submission_id: UUID,
    submission_in: AssemblySubmissionUpdate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Update an assembly submission."""

    submission = assembly_submission_service.get(db, id=submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Assembly submission not found")

    submission = assembly_submission_service.update(db, db_obj=submission, obj_in=submission_in)
    return submission


# ==========================================
# Assembly File endpoints
# ==========================================


@router.get("/{assembly_id}/files", response_model=List[AssemblyFileSchema])
def read_assembly_files(
    *,
    db: Session = Depends(get_db),
    assembly_id: UUID,
    file_type: Optional[str] = Query(None, description="Filter by file type"),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Get all files for an assembly."""
    assembly = assembly_service.get(db, id=assembly_id)
    if not assembly:
        raise HTTPException(status_code=404, detail="Assembly not found")

    if file_type:
        files = assembly_file_service.get_by_assembly_and_type(
            db, assembly_id=assembly_id, file_type=file_type
        )
    else:
        files = assembly_file_service.get_by_assembly_id(db, assembly_id=assembly_id)

    return files


@router.post("/{assembly_id}/files", response_model=AssemblyFileSchema)
@policy("assemblies:write")
def create_assembly_file(
    *,
    db: Session = Depends(get_db),
    assembly_id: UUID,
    file_in: AssemblyFileCreate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Add a file to an assembly."""

    # Verify assembly exists
    assembly = assembly_service.get(db, id=assembly_id)
    if not assembly:
        raise HTTPException(status_code=404, detail="Assembly not found")

    # Ensure assembly_id matches
    if file_in.assembly_id != assembly_id:
        raise HTTPException(status_code=400, detail="Assembly ID mismatch")

    file = assembly_file_service.create(db, obj_in=file_in)
    return file


@router.put("/files/{file_id}", response_model=AssemblyFileSchema)
@policy("assemblies:write")
def update_assembly_file(
    *,
    db: Session = Depends(get_db),
    file_id: UUID,
    file_in: AssemblyFileUpdate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Update an assembly file."""

    file = assembly_file_service.get(db, id=file_id)
    if not file:
        raise HTTPException(status_code=404, detail="Assembly file not found")

    file = assembly_file_service.update(db, db_obj=file, obj_in=file_in)
    return file


@router.delete("/files/{file_id}")
@policy("assemblies:delete")
def delete_assembly_file(
    *,
    db: Session = Depends(get_db),
    file_id: UUID,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Delete an assembly file."""
    file = assembly_file_service.get(db, id=file_id)
    if not file:
        raise HTTPException(status_code=404, detail="Assembly file not found")

    assembly_file_service.remove(db, id=file_id)
    return {"message": "File deleted successfully"}

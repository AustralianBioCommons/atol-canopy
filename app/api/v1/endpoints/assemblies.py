import logging
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, joinedload

from app.api.v1.endpoints.qc_reads import _build_prepared_payload
from app.core.dependencies import get_current_active_user, get_db
from app.core.errors import AppError
from app.core.pagination import Pagination, apply_pagination, pagination_params
from app.core.policy import policy
from app.models.assembly import (
    Assembly,
    AssemblyFile,
    AssemblyRun,
    AssemblyStageRun,
    AssemblySubmission,
)
from app.models.experiment import Experiment
from app.models.organism import Organism
from app.models.qc_read import QcRead, QcReadAssembly, QcReadFile, QcReadSubmission
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
    AssemblyIntentCancel,
    AssemblyRunCreate,
    AssemblyRunOut,
    AssemblySpecimenSampleDiscoveryResponse,
    AssemblyStageRunCreate,
    AssemblyStageRunOut,
    AssemblyStageRunUpdate,
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
from app.schemas.qc_read import QcCallbackRequest, QcReadOut, classify_reported_files
from app.services.assembly_helper import (
    determine_assembly_data_types,
    generate_assembly_manifest_json,
    get_available_assembly_data_types,
)
from app.services.assembly_service import (
    assembly_file_service,
    assembly_run_service,
    assembly_service,
    assembly_stage_run_service,
    assembly_submission_service,
)
from app.services.organism_service import organism_service

router = APIRouter()
logger = logging.getLogger(__name__)

_ASSEMBLY_MUTABLE_FIELDS = {
    column.name
    for column in Assembly.__table__.columns
    if column.name not in {"id", "created_at", "updated_at"}
}


# TODO remove tax_id refs and rely solely on taxon_id in organism table for all relationships and queries.
def _organism_taxon_id(organism: Any) -> int:
    return organism.taxon_id if hasattr(organism, "taxon_id") else organism.tax_id


def _build_sample_metadata_by_id(
    db: Session, experiments: List[Experiment]
) -> Dict[str, Dict[str, Any]]:
    """Build sample metadata mapping used in per-read manifest entries."""
    sample_ids = {exp.sample_id for exp in experiments if getattr(exp, "sample_id", None)}
    if not sample_ids:
        return {}

    sample_rows = db.query(Sample).filter(Sample.id.in_(list(sample_ids))).all()
    return {
        str(sample.id): {
            "bpa_sample_id": getattr(sample, "bpa_sample_id", None),
            "specimen_id": getattr(sample, "specimen_id", None),
        }
        for sample in sample_rows
    }


def _build_specimen_metadata(*samples: Sample) -> Dict[str, Dict[str, Any]]:
    return {
        str(sample.id): {
            "bpa_sample_id": getattr(sample, "bpa_sample_id", None),
            "specimen_id": getattr(sample, "specimen_id", None),
            "tolid": getattr(sample, "tolid", None),
        }
        for sample in samples
        if sample is not None
    }


def _validate_specimen_sample(
    db: Session, sample_id: UUID, taxon_id: int, field_name: str
) -> Sample:
    """Validate a specimen sample: must exist, kind='specimen', and belong to taxon_id."""
    sample = db.query(Sample).filter(Sample.id == sample_id).first()
    if not sample:
        raise AppError(
            status_code=422,
            code="specimen_sample_not_found",
            message=f"{field_name} not found",
            details={"field": field_name, "sample_id": str(sample_id)},
        )
    if sample.kind != "specimen":
        raise AppError(
            status_code=422,
            code="specimen_sample_invalid_kind",
            message=f"{field_name} must be a specimen sample (kind='specimen'), got kind='{sample.kind}'",
            details={"field": field_name, "sample_id": str(sample_id), "kind": sample.kind},
        )
    if sample.taxon_id != taxon_id:
        raise AppError(
            status_code=422,
            code="specimen_sample_taxon_mismatch",
            message=f"{field_name} does not belong to taxon_id {taxon_id}",
            details={
                "field": field_name,
                "sample_id": str(sample_id),
                "sample_taxon_id": sample.taxon_id,
                "expected_taxon_id": taxon_id,
            },
        )
    return sample


def _get_lineage_sample_ids_for_specimen(db: Session, specimen_sample: Sample) -> List[UUID]:
    """Return specimen sample id plus any derived samples linked from it."""
    derived_samples = (
        db.query(Sample)
        .filter(
            Sample.derived_from_sample_id == specimen_sample.id,
            Sample.taxon_id == specimen_sample.taxon_id,
            Sample.kind == "derived",
        )
        .all()
    )
    return [specimen_sample.id] + [sample.id for sample in derived_samples]


def _get_allowed_sample_ids_for_assembly(db: Session, assembly: Assembly) -> Set[UUID]:
    """Return the specimen-sample lineage ids that are valid inputs for an assembly."""
    allowed_sample_ids: Set[UUID] = set()

    if assembly.long_read_specimen_sample_id:
        long_read_sample = (
            db.query(Sample).filter(Sample.id == assembly.long_read_specimen_sample_id).first()
        )
        if long_read_sample:
            allowed_sample_ids.update(_get_lineage_sample_ids_for_specimen(db, long_read_sample))

    hic_specimen_sample_ids = assembly.hic_specimen_sample_ids or []
    for hic_sample_id in hic_specimen_sample_ids:
        hic_sample = db.query(Sample).filter(Sample.id == hic_sample_id).first()
        if hic_sample:
            allowed_sample_ids.update(_get_lineage_sample_ids_for_specimen(db, hic_sample))

    return allowed_sample_ids


def _assembly_manifest_package_ids(assembly: Assembly) -> Set[str]:
    manifest = assembly.manifest_json or {}
    read_files = manifest.get("read_files") or []
    return {entry["name"] for entry in read_files if isinstance(entry, dict) and entry.get("name")}


@router.get("/specimen-samples/{taxon_id}", response_model=AssemblySpecimenSampleDiscoveryResponse)
def get_specimen_samples_for_assembly(
    *,
    db: Session = Depends(get_db),
    taxon_id: int,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Return specimen samples and available assembly data types for a taxon."""
    organism = db.query(Organism).filter(Organism.taxon_id == taxon_id).first()
    if not organism:
        raise HTTPException(status_code=404, detail=f"Organism with taxon_id {taxon_id} not found")

    organism_taxon_id = _organism_taxon_id(organism)
    specimen_samples = (
        db.query(Sample)
        .filter(Sample.taxon_id == organism_taxon_id, Sample.kind == "specimen")
        .all()
    )

    specimen_sample_options = []
    for specimen_sample in specimen_samples:
        lineage_sample_ids = _get_lineage_sample_ids_for_specimen(db, specimen_sample)
        experiments = (
            db.query(Experiment).filter(Experiment.sample_id.in_(lineage_sample_ids)).all()
        )

        specimen_sample_options.append(
            {
                "sample_id": specimen_sample.id,
                "specimen_id": specimen_sample.specimen_id,
                "sex": specimen_sample.sex,
                "available_data_types": get_available_assembly_data_types(experiments),
            }
        )

    return {
        "taxon_id": organism_taxon_id,
        "specimen_samples": specimen_sample_options,
    }


@router.get("/pipeline-inputs")
def get_pipeline_inputs(
    *,
    db: Session = Depends(get_db),
    taxon_id: int = Query(None, description="Organism taxon_id to filter by"),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get pipeline inputs for an organism by taxon_id.

    Returns a list of objects with scientific_name and files mapping for each organism.
    Files mapping contains read file names as keys and their bioplatforms_urls as values.
    """
    if taxon_id is None:
        raise HTTPException(status_code=422, detail="taxon_id query parameter is required")
    if db is None:
        raise HTTPException(status_code=422, detail="database session is required")
    organism = organism_service.get_by_taxon_id(db, taxon_id)
    if not organism:
        raise HTTPException(
            status_code=404, detail=f"Organism with taxon_id '{taxon_id}' not found"
        )

    organism_taxon_id = _organism_taxon_id(organism)
    samples = db.query(Sample).filter(Sample.taxon_id == organism_taxon_id).all()
    if not samples:
        return [
            {
                "scientific_name": organism.scientific_name,
                "taxon_id": organism_taxon_id,
                "files": {},
            }
        ]

    result = []
    files_dict = {}

    for sample in samples:
        experiments = db.query(Experiment).filter(Experiment.sample_id == sample.id).all()
        for experiment in experiments:
            reads = db.query(Read).filter(Read.experiment_id == experiment.id).all()
            if reads is None:
                continue
            for read in reads:
                if read.file_name and read.bioplatforms_url:
                    files_dict[read.file_name] = read.bioplatforms_url

    result.append(
        {
            "scientific_name": organism.scientific_name,
            "taxon_id": organism_taxon_id,
            "files": files_dict,
        }
    )
    return result


@router.get("/pipeline-inputs-by-tax-id")
def get_pipeline_inputs_by_taxon_id(
    *,
    db: Session = Depends(get_db),
    taxon_id: str = Query(None, description="Organism tax ID to filter by"),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get pipeline inputs for organisms by taxon_id.

    Returns a nested structure with taxon_id as the top level key,
    and scientific_name and files mapping for that organism.
    """
    if taxon_id is None:
        raise HTTPException(status_code=422, detail="taxon_id query parameter is required")

    organism = organism_service.get_by_taxon_id(db, int(taxon_id))
    if not organism:
        return {taxon_id: {}}

    result = {taxon_id: {"scientific_name": organism.scientific_name, "files": {}}}
    organism_taxon_id = _organism_taxon_id(organism)
    samples = db.query(Sample).filter(Sample.taxon_id == organism_taxon_id).all()
    if not samples:
        return result

    for sample in samples:
        experiments = db.query(Experiment).filter(Experiment.sample_id == sample.id).all()
        for experiment in experiments:
            reads = db.query(Read).filter(Read.experiment_id == experiment.id).all()
            for read in reads:
                if read.file_name and read.bioplatforms_url:
                    result[taxon_id]["files"][read.file_name] = read.bioplatforms_url

    return result


@router.get("/manifest/{taxon_id}")
def get_assembly_manifest(
    *,
    db: Session = Depends(get_db),
    taxon_id: int,
    version: Optional[int] = Query(None, description="Assembly version to retrieve"),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Retrieve the stored manifest JSON for the latest assembly for a taxon.

    Returns the manifest that was generated and stored when the intent was created.
    """
    organism = db.query(Organism).filter(Organism.taxon_id == taxon_id).first()
    if not organism:
        raise HTTPException(status_code=404, detail=f"Organism with taxon_id {taxon_id} not found")

    assembly_query = (
        db.query(Assembly)
        .filter(Assembly.taxon_id == _organism_taxon_id(organism))
        .order_by(Assembly.created_at.desc())
    )
    if version is not None:
        assembly_query = assembly_query.filter(Assembly.version == version)
    assembly = assembly_query.first()
    if not assembly:
        raise HTTPException(status_code=404, detail="No assembly manifest found")

    if assembly.manifest_json is None:
        logger.error(
            "Assembly %s for taxon_id %s has no manifest_json; returning empty manifest",
            assembly.id,
            taxon_id,
        )

    return JSONResponse(
        content={
            "assembly_id": str(assembly.id),
            "version": assembly.version,
            "manifest": assembly.manifest_json or {},
        }
    )


@router.post("/intent/{taxon_id}")
@policy("assemblies:write")
def create_assembly_intent(
    *,
    db: Session = Depends(get_db),
    taxon_id: int,
    intent_in: AssemblyIntent = Body(...),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Create an assembly record using explicit specimen sample IDs and return its manifest as JSON.

    The caller must supply:
    - long_read_specimen_sample_id: the specimen sample used for PacBio / ONT long reads
    - hic_specimen_sample_id (optional): the specimen sample used for Hi-C reads

    Both samples must be kind='specimen' and belong to the given taxon_id.

    Returns JSON with assembly_id, version, and the generated manifest.
    """
    # 1. Resolve organism
    organism_query = db.query(Organism)
    if hasattr(organism_query, "options"):
        organism_query = organism_query.options(joinedload(Organism.taxonomy_info))
    organism = organism_query.filter(Organism.taxon_id == taxon_id).first()
    if not organism:
        raise HTTPException(status_code=404, detail=f"Organism with taxon_id {taxon_id} not found")
    org_taxon_id = _organism_taxon_id(organism)

    # 2. Validate long_read_specimen_sample_id
    long_read_sample = _validate_specimen_sample(
        db, intent_in.long_read_specimen_sample_id, org_taxon_id, "long_read_specimen_sample_id"
    )

    # 3. Validate hic_specimen_sample_ids if provided
    hic_samples: List[Sample] = []
    if intent_in.hic_specimen_sample_ids:
        for idx, hic_sid in enumerate(intent_in.hic_specimen_sample_ids):
            hic_samples.append(
                _validate_specimen_sample(
                    db, hic_sid, org_taxon_id, f"hic_specimen_sample_ids[{idx}]"
                )
            )

    # 4. Fetch long-read experiments (PacBio or ONT only) and their reads
    long_read_lineage_sample_ids = _get_lineage_sample_ids_for_specimen(db, long_read_sample)
    long_read_sample_id_map = {
        str(sample_id): str(long_read_sample.id) for sample_id in long_read_lineage_sample_ids
    }
    long_read_experiments = (
        db.query(Experiment)
        .filter(
            Experiment.sample_id.in_(long_read_lineage_sample_ids),
            Experiment.platform.in_(["PACBIO_SMRT", "OXFORD_NANOPORE"]),
        )
        .all()
    )
    if not long_read_experiments:
        raise AppError(
            status_code=422,
            code="no_long_read_experiments",
            message="No long-read experiments (PacBio or ONT) found for long_read_specimen_sample_id",
            details={"long_read_specimen_sample_id": str(long_read_sample.id)},
        )

    long_read_exp_ids = [e.id for e in long_read_experiments]
    long_reads = db.query(Read).filter(Read.experiment_id.in_(long_read_exp_ids)).all()

    # 5. Fetch Hi-C experiments and reads for each hic_sample
    hic_experiments: List[Experiment] = []
    hic_reads: List[Read] = []
    hic_sample_id_map: Dict[str, str] = {}
    for hic_sample in hic_samples:
        hic_lineage_sample_ids = _get_lineage_sample_ids_for_specimen(db, hic_sample)
        hic_sample_id_map.update(
            {str(sample_id): str(hic_sample.id) for sample_id in hic_lineage_sample_ids}
        )
        hic_exps = (
            db.query(Experiment)
            .filter(
                Experiment.sample_id.in_(hic_lineage_sample_ids),
                Experiment.platform == "ILLUMINA",
            )
            .all()
        )
        hic_exps = [e for e in hic_exps if (e.library_strategy or "").upper() == "HI-C"]
        if not hic_exps:
            raise AppError(
                status_code=422,
                code="no_hic_experiments",
                message="No Hi-C experiments (ILLUMINA + Hi-C) found for hic_specimen_sample_ids",
                details={"hic_specimen_sample_id": str(hic_sample.id)},
            )
        hic_exp_ids = [e.id for e in hic_exps]
        hic_experiments.extend(hic_exps)
        hic_reads.extend(db.query(Read).filter(Read.experiment_id.in_(hic_exp_ids)).all())

    # 6. Determine data_types from the relevant experiments
    # TODO review and remove this step now that we pass in the specimen_id
    all_experiments = long_read_experiments + hic_experiments
    try:
        data_types = determine_assembly_data_types(all_experiments)
    except ValueError as exc:
        raise AppError(
            status_code=400,
            code="assembly_intent_invalid_data_types",
            message=str(exc),
            details={"taxon_id": taxon_id},
        ) from exc

    # 7. Create assembly (version is assigned inside the service)
    assembly = assembly_service.create_from_intent(
        db,
        taxon_id=org_taxon_id,
        long_read_specimen_sample_id=long_read_sample.id,
        hic_specimen_sample_ids=[s.id for s in hic_samples] if hic_samples else None,
        # TODO review if we need data_types when creating experiment
        data_types=data_types,
        tol_id=intent_in.tol_id,
        project_id=None,
        manifest_json=None,  # filled in step 9
    )

    try:
        # 8. Build sample metadata and generate JSON manifest
        all_reads = long_reads + hic_reads
        sample_metadata_by_id = _build_specimen_metadata(long_read_sample, *hic_samples)
        sequencing_sample_to_specimen_sample_id = {
            **long_read_sample_id_map,
            **hic_sample_id_map,
        }
        manifest_data = generate_assembly_manifest_json(
            organism=organism,
            taxonomy_info=getattr(organism, "taxonomy_info", None),
            reads=all_reads,
            experiments=all_experiments,
            # TODO tolid from sample (reported by broker) not input from caller
            tol_id=assembly.tol_id,
            assembly_id=str(assembly.id),
            version=assembly.version,
            long_read_sample_id=long_read_sample.id,
            hic_sample_ids=[s.id for s in hic_samples] if hic_samples else None,
            sample_metadata_by_id=sample_metadata_by_id,
            sequencing_sample_to_specimen_sample_id=sequencing_sample_to_specimen_sample_id,
        )

        # 9. Validate that the manifest contains eligible reads then persist it
        # TODO decide whether to keep this validation.
        """
        long_read_keys = {"PACBIO_SMRT", "OXFORD_NANOPORE"}
        if not any(k in manifest_data["read_files"] for k in long_read_keys):
            raise AppError(
                status_code=422,
                code="no_eligible_long_reads",
                message=(
                    "No eligible long reads found for long_read_specimen_sample_id. "
                    "PacBio reads must end in .ccs.bam or hifi_reads.bam."
                ),
                details={"long_read_specimen_sample_id": str(long_read_sample.id)},
            )

        if hic_samples and "Hi-C" not in manifest_data["read_files"]:
            raise AppError(
                status_code=422,
                code="no_eligible_hic_reads",
                message="No eligible Hi-C reads found for hic_specimen_sample_ids",
                details={"hic_specimen_sample_ids": [str(s.id) for s in hic_samples]},
            )
        """
        assembly.manifest_json = manifest_data
        db.add(assembly)
        db.commit()
        db.refresh(assembly)
    except Exception:
        db.delete(assembly)
        db.commit()
        raise

    return JSONResponse(
        content={
            "assembly_id": str(assembly.id),
            "version": assembly.version,
            "manifest": manifest_data,
        }
    )


@router.post("/intent/{taxon_id}/cancel")
@policy("assemblies:write")
def cancel_assembly_intent(
    *,
    db: Session = Depends(get_db),
    taxon_id: int,
    cancel_in: AssemblyIntentCancel,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Delete an assembly intent by ID."""
    organism = db.query(Organism).filter(Organism.taxon_id == taxon_id).first()
    if not organism:
        raise HTTPException(status_code=404, detail=f"Organism with taxon_id {taxon_id} not found")

    assembly = (
        db.query(Assembly)
        .filter(
            Assembly.id == cancel_in.assembly_id,
            Assembly.taxon_id == _organism_taxon_id(organism),
        )
        .first()
    )
    if not assembly:
        raise HTTPException(status_code=404, detail="Assembly not found to cancel")
    if cancel_in.version is not None and cancel_in.version != assembly.version:
        raise AppError(
            status_code=409,
            code="assembly_intent_version_mismatch",
            message="Requested version does not match the assembly",
            details={
                "assembly_id": str(assembly.id),
                "requested_version": cancel_in.version,
                "actual_version": assembly.version,
            },
        )

    response = {
        "id": str(assembly.id),
        "taxon_id": assembly.taxon_id,
        "long_read_specimen_sample_id": str(assembly.long_read_specimen_sample_id)
        if assembly.long_read_specimen_sample_id
        else None,
        "hic_specimen_sample_ids": assembly.hic_specimen_sample_ids or [],
        "version": assembly.version,
        "deleted": True,
    }
    db.delete(assembly)
    db.commit()
    return response


@router.get("/optimal-sample/{taxon_id}")
def get_optimal_sample_id(
    *,
    db: Session = Depends(get_db),
    taxon_id: int,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Return the first specimen sample for an organism (informational helper)."""
    sample = (
        db.query(Sample)
        .filter(Sample.taxon_id == taxon_id, Sample.kind == "specimen")
        .order_by(Sample.created_at.asc())
        .first()
    )
    return {"sample_id": str(sample.id) if sample else None}


@router.post("/from-experiments/{taxon_id}", response_model=AssemblySchema)
@policy("assemblies:write")
def create_assembly_from_experiments(
    *,
    db: Session = Depends(get_db),
    taxon_id: int,
    assembly_in: AssemblyCreateFromExperiments,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Create assembly based on all experiments for an organism (by taxon_id).

    Automatically determines data_types by analyzing experiment platforms.
    The data_types field is auto-detected but can be overridden.
    """
    try:
        assembly, platform_info = assembly_service.create_from_experiments(
            db, taxon_id=taxon_id, assembly_in=assembly_in
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


@router.get("/{assembly_id}/manifest")
def get_manifest_by_assembly_id(
    *,
    db: Session = Depends(get_db),
    assembly_id: UUID,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Retrieve the stored manifest JSON for a specific assembly."""
    assembly = db.query(Assembly).filter(Assembly.id == assembly_id).first()
    if not assembly:
        raise HTTPException(status_code=404, detail="Assembly not found")

    if assembly.manifest_json is None:
        raise HTTPException(
            status_code=404,
            detail="No manifest stored for this assembly. Re-submit an intent to generate one.",
        )

    return JSONResponse(
        content={
            "assembly_id": str(assembly.id),
            "version": assembly.version,
            "manifest": assembly.manifest_json,
        }
    )


@router.get("/{assembly_id}", response_model=AssemblySchema)
def read_assembly(
    *,
    db: Session = Depends(get_db),
    assembly_id: UUID,
    current_user: User = Depends(get_current_active_user),
) -> Any:
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

    update_data = assembly_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field not in _ASSEMBLY_MUTABLE_FIELDS:
            continue
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
    assembly = assembly_service.get(db, id=assembly_id)
    if not assembly:
        raise HTTPException(status_code=404, detail="Assembly not found")
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


# ==========================================
# Assembly Run endpoints (pipeline invocations)
# ==========================================


@router.get("/{assembly_id}/runs", response_model=List[AssemblyRunOut])
def list_assembly_runs(
    *,
    db: Session = Depends(get_db),
    assembly_id: UUID,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """List all pipeline runs for an assembly, newest first."""
    assembly = assembly_service.get(db, id=assembly_id)
    if not assembly:
        raise HTTPException(status_code=404, detail="Assembly not found")
    return assembly_run_service.get_by_assembly_id(db, assembly_id=assembly_id)


@router.post("/{assembly_id}/runs", response_model=AssemblyRunOut)
@policy("assemblies:write")
def create_assembly_run(
    *,
    db: Session = Depends(get_db),
    assembly_id: UUID,
    run_in: AssemblyRunCreate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Register a new pipeline invocation for an assembly (github_repo + git_commit)."""
    assembly = assembly_service.get(db, id=assembly_id)
    if not assembly:
        raise HTTPException(status_code=404, detail="Assembly not found")
    return assembly_run_service.create_for_assembly(
        db,
        assembly_id=assembly_id,
        run_in=run_in,
    )


@router.post("/{assembly_id}/qc-reads/report", response_model=QcReadOut, status_code=201)
@policy("qc_reads:report")
def report_assembly_qc_read(
    *,
    db: Session = Depends(get_db),
    assembly_id: UUID,
    payload: QcCallbackRequest,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Create a QC read result for an assembly from one or two source read MD5 sums."""
    assembly = assembly_service.get(db, id=assembly_id)
    if not assembly:
        raise HTTPException(status_code=404, detail="Assembly not found")

    experiment = (
        db.query(Experiment).filter(Experiment.bpa_package_id == payload.bpa_package_id).first()
    )
    if not experiment:
        raise HTTPException(
            status_code=422,
            detail=f"Experiment not found for bpa_package_id: {payload.bpa_package_id}",
        )

    allowed_sample_ids = _get_allowed_sample_ids_for_assembly(db, assembly)
    sample = db.query(Sample).filter(Sample.id == experiment.sample_id).first()
    if not sample or sample.derived_from_sample_id not in allowed_sample_ids:
        lineage_lookup = _get_assembly_lineage_debug_details(db, assembly)
        logger.warning(
            "QC read lineage validation failed: assembly_id=%s bpa_package_id=%s "
            "experiment_id=%s experiment_sample_id=%s "
            "experiment_specimen_sample_id=%s allowed_sample_ids=%s lineage_lookup=%s",
            str(assembly.id),
            payload.bpa_package_id,
            str(experiment.id),
            str(experiment.sample_id) if experiment.sample_id else None,
            str(sample.derived_from_sample_id) if sample else None,
            sorted(str(sample_id) for sample_id in allowed_sample_ids),
            allowed_sample_ids,
        )
        raise HTTPException(
            status_code=422,
            detail=(
                "Experiment sample is not part of the target assembly specimen lineage "
                f"for bpa_package_id: {payload.bpa_package_id}"
            ),
        )

    manifest_package_ids = _assembly_manifest_package_ids(assembly)
    if payload.bpa_package_id not in manifest_package_ids:
        raise HTTPException(
            status_code=422,
            detail=(
                "Experiment is not present in the target assembly manifest inputs "
                f"for bpa_package_id: {payload.bpa_package_id}"
            ),
        )

    source_reads = (
        db.query(Read)
        .filter(
            Read.experiment_id == experiment.id,
            Read.file_checksum.in_(payload.source_read_file_checksums),
        )
        .all()
    )
    matched_md5s = {read.file_checksum for read in source_reads if read.file_checksum}
    missing_md5s = sorted(set(payload.source_read_file_checksums) - matched_md5s)
    if missing_md5s:
        raise HTTPException(
            status_code=422,
            detail=(
                "Source read MD5 sums are not linked to the experiment for "
                f"bpa_package_id: {payload.bpa_package_id}. Missing MD5 sums: {missing_md5s}"
            ),
        )

    qc_read = QcRead(
        experiment_id=experiment.id,
        source_read_file_checksums=payload.source_read_file_checksums,
        base_count=payload.base_count,
        read_count=payload.read_count,
        qc_bases_removed=payload.qc_bases_removed,
        qc_reads_removed=payload.qc_reads_removed,
        mean_gc_content=payload.mean_gc_content,
        n50_length=payload.n50_length,
    )
    db.add(qc_read)
    db.flush()

    db.add(QcReadAssembly(assembly_id=assembly_id, qc_read_id=qc_read.id))

    reported_files = classify_reported_files(payload.checksums)
    qc_files = [
        QcReadFile(
            qc_read_id=qc_read.id,
            file_type=f.file_type,
            storage_backend=None,
            storage_profile=None,
            bucket_name=None,
            path_to_file=f.path_to_file,
            md5_checksum=f.md5_checksum,
            sha256_checksum=f.sha256_checksum,
        )
        for f in reported_files
    ]
    for qf in qc_files:
        db.add(qf)
    db.flush()

    db.add(
        QcReadSubmission(
            qc_read_id=qc_read.id,
            authority="ENA",
            status="draft",
            prepared_payload=_build_prepared_payload(qc_read, qc_files),
            entity_type_const="qc_read",
        )
    )
    db.commit()
    db.refresh(qc_read)
    return qc_read


# ==========================================
# Assembly Stage Run endpoints
# ==========================================


@router.get("/{assembly_id}/runs/{run_id}/stage-runs", response_model=List[AssemblyStageRunOut])
def list_stage_runs(
    *,
    db: Session = Depends(get_db),
    assembly_id: UUID,
    run_id: UUID,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """List all stage runs for a pipeline run, newest first."""
    assembly_run = (
        db.query(AssemblyRun)
        .filter(AssemblyRun.id == run_id, AssemblyRun.assembly_id == assembly_id)
        .first()
    )
    if not assembly_run:
        raise HTTPException(status_code=404, detail="Assembly run not found")
    return assembly_stage_run_service.get_by_assembly_run_id(db, assembly_run_id=run_id)


@router.post("/{assembly_id}/runs/{run_id}/stage-runs", response_model=AssemblyStageRunOut)
@policy("assemblies:write")
def create_stage_run(
    *,
    db: Session = Depends(get_db),
    assembly_id: UUID,
    run_id: UUID,
    run_in: AssemblyStageRunCreate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Report a stage result for a pipeline run."""
    assembly_run = (
        db.query(AssemblyRun)
        .filter(AssemblyRun.id == run_id, AssemblyRun.assembly_id == assembly_id)
        .first()
    )
    if not assembly_run:
        raise HTTPException(status_code=404, detail="Assembly run not found")
    return assembly_stage_run_service.create_with_files(
        db,
        assembly_run_id=run_id,
        run_in=run_in,
    )


@router.patch(
    "/{assembly_id}/runs/{run_id}/stage-runs/{stage_run_id}",
    response_model=AssemblyStageRunOut,
)
@policy("assemblies:write")
def update_stage_run(
    *,
    db: Session = Depends(get_db),
    assembly_id: UUID,
    run_id: UUID,
    stage_run_id: UUID,
    update_in: AssemblyStageRunUpdate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Update status, stats, or files for an existing stage run."""
    stage_run = (
        db.query(AssemblyStageRun)
        .filter(
            AssemblyStageRun.id == stage_run_id,
            AssemblyStageRun.assembly_run_id == run_id,
        )
        .join(AssemblyRun)
        .filter(AssemblyRun.assembly_id == assembly_id)
        .first()
    )
    if not stage_run:
        raise HTTPException(status_code=404, detail="Stage run not found")
    return assembly_stage_run_service.update_with_files(db, db_obj=stage_run, update_in=update_in)

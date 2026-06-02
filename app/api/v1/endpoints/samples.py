import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_active_user, get_db
from app.core.pagination import Pagination, apply_pagination, pagination_params
from app.core.policy import policy
from app.models.experiment import Experiment
from app.models.organism import Organism
from app.models.project import Project
from app.models.qc_read import QcRead
from app.models.read import Read
from app.models.sample import Sample, SampleSubmission
from app.models.user import User
from app.schemas.bulk_import import BulkImportResponse, BulkSampleImport
from app.schemas.common import SampleKind, SubmissionJsonResponse, SubmissionStatus
from app.schemas.sample import Sample as SampleSchema
from app.schemas.sample import (
    SampleCreate,
    SampleSubmissionCreate,
    SampleSubmissionUpdate,
    SampleUpdate,
    SpecimenSampleHierarchyResponse,
)
from app.schemas.sample import SampleSubmission as SampleSubmissionSchema
from app.utils.mapping import to_float

router = APIRouter()

_SAMPLE_MAPPING_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "config",
    "ena-atol-map.json",
)
_SAMPLE_NUMERIC_FIELDS = {"latitude", "longitude", "elevation", "depth"}
_SAMPLE_REQUIRED_TEXT_DEFAULTS = {
    "lifestage": "unknown",
    "sex": "unknown",
    "organism_part": "unknown",
    "region_and_locality": "unknown",
    "country_or_sea": "unknown",
    "habitat": "unknown",
    "collected_by": "unknown",
    "collecting_institution": "unknown",
}
_SAMPLE_TEXT_FIELDS = {
    "bpa_sample_id",
    "specimen_id",
    "specimen_id_description",
    "identified_by",
    "specimen_custodian",
    "sample_custodian",
    "collection_method",
    "collection_date",
    "collection_permit",
    "data_context",
    "bioplatforms_project_id",
    "title",
    "sample_same_as",
    "sample_derived_from",
    "specimen_voucher",
    "tolid",
    "preservation_method",
    "preservation_temperature",
    "project_name",
    "biosample_accession",
    "state_or_region",
    "indigenous_location",
}
_SAMPLE_MUTABLE_FIELDS = (
    set(_SAMPLE_REQUIRED_TEXT_DEFAULTS)
    | _SAMPLE_TEXT_FIELDS
    | _SAMPLE_NUMERIC_FIELDS
    | {"taxon_id", "derived_from_sample_id", "kind", "extensions"}
)


def _organism_taxon_id(organism: Any) -> int:
    return organism.taxon_id if hasattr(organism, "taxon_id") else organism.tax_id


def _get_genomic_data_project_id(db: Session, taxon_id: int) -> UUID:
    """Get the genomic_data project ID for an organism."""
    project = (
        db.query(Project)
        .filter(Project.taxon_id == taxon_id, Project.project_type == "genomic_data")
        .first()
    )
    if not project:
        raise HTTPException(
            status_code=404, detail=f"No genomic_data project found for taxon_id {taxon_id}"
        )
    return project.id


def _load_sample_mapping() -> Dict[str, Any]:
    with open(_SAMPLE_MAPPING_PATH, "r") as f:
        return json.load(f)


def _build_sample_prepared_payload(sample_data: Dict[str, Any]) -> Dict[str, Any]:
    ena_atol_map = _load_sample_mapping()
    prepared_payload = {}
    for ena_key, atol_key in ena_atol_map["sample"].items():
        if atol_key in sample_data:
            prepared_payload[ena_key] = sample_data[atol_key]
    return prepared_payload


def _validate_sample_lineage(
    db: Session,
    *,
    sample_id: Optional[UUID],
    taxon_id: Optional[int],
    kind: SampleKind,
    specimen_id: Optional[str],
    derived_from_sample_id: Optional[UUID],
) -> None:
    if kind == SampleKind.DERIVED and not derived_from_sample_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Derived samples must have a parent sample (derived_from_sample_id)",
        )
    if kind == SampleKind.SPECIMEN and derived_from_sample_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Specimen samples cannot have a parent sample",
        )
    if sample_id and derived_from_sample_id == sample_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A sample cannot be its own parent",
        )

    if kind == SampleKind.SPECIMEN and specimen_id:
        existing_specimen = (
            db.query(Sample)
            .filter(
                Sample.taxon_id == taxon_id,
                Sample.specimen_id == specimen_id,
                Sample.kind == SampleKind.SPECIMEN,
            )
            .first()
        )
        if existing_specimen and existing_specimen.id != sample_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Specimen sample already exists for taxon_id '{taxon_id}' "
                f"and specimen_id '{specimen_id}' (sample_id: {existing_specimen.id})",
            )

    if derived_from_sample_id:
        parent_sample = db.query(Sample).filter(Sample.id == derived_from_sample_id).first()
        if not parent_sample:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Parent sample with id {derived_from_sample_id} not found",
            )
        if parent_sample.kind != SampleKind.SPECIMEN:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parent sample must be of kind 'specimen'",
            )
        if taxon_id is not None and parent_sample.taxon_id != taxon_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parent sample must belong to the same taxon_id",
            )


@router.get("/", response_model=List[SampleSchema])
def read_samples(
    db: Session = Depends(get_db),
    pagination: Pagination = Depends(pagination_params),
    taxon_id: Optional[int] = Query(None, description="Filter by organism taxon ID"),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Retrieve samples.
    """
    # All users can read samples
    query = db.query(Sample)
    if taxon_id:
        query = query.filter(Sample.taxon_id == taxon_id)

    samples = apply_pagination(query, pagination).all()
    return samples


@router.get(
    "/by-specimen/{taxon_id}/{specimen_id:path}/related",
    response_model=SpecimenSampleHierarchyResponse,
)
def get_samples_experiments_and_reads_for_specimen(
    *,
    db: Session = Depends(get_db),
    taxon_id: int,
    specimen_id: str,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Return the specimen sample, related samples, and nested experiments/reads."""
    organism = db.query(Organism).filter(Organism.taxon_id == taxon_id).first()
    if not organism:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organism with taxon_id {taxon_id} not found",
        )

    specimen_sample = (
        db.query(Sample)
        .filter(
            Sample.taxon_id == organism.taxon_id,
            Sample.specimen_id == specimen_id,
            Sample.kind == SampleKind.SPECIMEN,
        )
        .first()
    )
    if not specimen_sample:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Specimen sample not found for taxon_id {taxon_id} and specimen_id '{specimen_id}'",
        )

    related_samples = (
        db.query(Sample)
        .filter(
            Sample.taxon_id == organism.taxon_id,
            or_(
                Sample.id == specimen_sample.id, Sample.derived_from_sample_id == specimen_sample.id
            ),
        )
        .all()
    )

    related_payload = []
    for sample in related_samples:
        experiments = db.query(Experiment).filter(Experiment.sample_id == sample.id).all()
        experiment_payload = []
        for experiment in experiments:
            reads = db.query(Read).filter(Read.experiment_id == experiment.id).all()
            qc_reads = (
                db.query(QcRead)
                .filter(QcRead.experiment_id == experiment.id)
                .all()
            )
            experiment_payload.append(
                {"experiment": experiment, "reads": reads, "qc_reads": qc_reads}
            )

        related_payload.append({"sample": sample, "experiments": experiment_payload})

    return {
        "taxon_id": organism.taxon_id,
        "specimen_id": specimen_id,
        "samples": related_payload,
    }


@router.get("/by-specimen/{taxon_id}/{specimen_id:path}", response_model=SampleSchema)
def get_specimen_by_taxid_and_specimen_id(
    *,
    db: Session = Depends(get_db),
    taxon_id: int,
    specimen_id: str,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Lookup a specimen sample by taxon_id and specimen_id.

    This finds the unique specimen sample for a given organism (by taxon_id)
    and specimen_id combination.
    """
    organism = db.query(Organism).filter(Organism.taxon_id == taxon_id).first()
    if not organism:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organism with taxon_id {taxon_id} not found",
        )

    sample = (
        db.query(Sample)
        .filter(
            Sample.taxon_id == organism.taxon_id,
            Sample.specimen_id == specimen_id,
            Sample.kind == SampleKind.SPECIMEN,
        )
        .first()
    )

    if not sample:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Specimen sample not found for taxon_id {taxon_id} and specimen_id '{specimen_id}'",
        )

    return sample


@router.post("/", response_model=SampleSchema)
@policy("samples:create")
def create_sample(
    *,
    db: Session = Depends(get_db),
    sample_in: SampleCreate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Create new sample.
    """
    sample_data = sample_in.model_dump(exclude_unset=True)
    sample_id = uuid.uuid4()

    # Build kwargs dynamically so we don't pass None for DB server_default columns
    # Determine sample kind and validate parent relationship
    kind = sample_in.kind or SampleKind.SPECIMEN
    derived_from_sample_id = sample_in.derived_from_sample_id

    _validate_sample_lineage(
        db,
        sample_id=sample_id,
        taxon_id=sample_in.taxon_id,
        kind=kind,
        specimen_id=sample_in.specimen_id,
        derived_from_sample_id=derived_from_sample_id,
    )

    sample_kwargs = dict(
        id=sample_id,
        taxon_id=sample_in.taxon_id,
        bpa_sample_id=sample_in.bpa_sample_id,
        specimen_id=sample_in.specimen_id,
        identified_by=sample_in.identified_by,
        specimen_id_description=sample_in.specimen_id_description,
        specimen_custodian=sample_in.specimen_custodian,
        sample_custodian=sample_in.sample_custodian,
        lifestage=sample_in.lifestage or "unknown",
        sex=sample_in.sex or "unknown",
        organism_part=sample_in.organism_part or "unknown",
        region_and_locality=sample_in.region_and_locality or "unknown",
        state_or_region=sample_in.state_or_region,
        country_or_sea=sample_in.country_or_sea or "unknown",
        indigenous_location=sample_in.indigenous_location,
        latitude=to_float(sample_in.latitude),
        longitude=to_float(sample_in.longitude),
        elevation=to_float(sample_in.elevation),
        depth=to_float(sample_in.depth),
        habitat=sample_in.habitat or "unknown",
        collected_by=sample_in.collected_by or "unknown",
        collecting_institution=sample_in.collecting_institution or "unknown",
        collection_method=sample_in.collection_method,
        collection_date=sample_in.collection_date or "unknown",
        collection_permit=sample_in.collection_permit,
        data_context=sample_in.data_context,
        bioplatforms_project_id=sample_in.bioplatforms_project_id,
        title=sample_in.title,
        sample_same_as=sample_in.sample_same_as,
        sample_derived_from=sample_in.sample_derived_from,
        specimen_voucher=sample_in.specimen_voucher,
        tolid=sample_in.tolid,
        preservation_method=sample_in.preservation_method,
        preservation_temperature=sample_in.preservation_temperature,
        # Parent-child relationship fields
        derived_from_sample_id=derived_from_sample_id,
        kind=kind,
        extensions=sample_in.extensions,
        # bpa_json=sample_in.model_dump(mode="json", exclude_unset=True),
    )

    sample = Sample(**sample_kwargs)
    db.add(sample)

    prepared_payload = _build_sample_prepared_payload(sample_data)

    # Get project_id for this organism
    project_id = _get_genomic_data_project_id(db, sample.taxon_id)

    sample_submission = SampleSubmission(
        sample_id=sample_id,
        authority="ENA",
        entity_type_const="sample",
        prepared_payload=prepared_payload,
        status=SubmissionStatus.DRAFT,
        project_id=project_id,
    )
    db.add(sample_submission)
    db.commit()
    db.refresh(sample)
    db.refresh(sample_submission)
    return sample


# Helper function for bulk import operations
def _create_sample_with_submission(
    db: Session,
    bpa_sample_id: Optional[str],
    sample_data: Dict[str, Any],
    taxon_id: int,
    kind: SampleKind,
    derived_from_sample_id: Optional[UUID] = None,
    ena_atol_map: Optional[Dict] = None,
) -> tuple[Sample, SampleSubmission]:
    """
    Helper function to create a sample and its submission record.

    bpa_sample_id is optional for specimen samples but required for derived samples.

    Returns:
        Tuple of (Sample, SampleSubmission)

    Raises:
        ValueError: If validation fails
    """
    sample_id = uuid.uuid4()

    # Required fields with fallbacks
    lifestage = sample_data.get("lifestage") or "unknown"
    sex = sample_data.get("sex") or "unknown"
    organism_part = sample_data.get("organism_part") or "unknown"

    region_and_locality = getattr(sample_data, "region_and_locality", None) or "unknown"
    country_or_sea = getattr(sample_data, "country_or_sea", None) or "unknown"
    habitat = sample_data.get("habitat") or "unknown"
    collection_date_val = getattr(sample_data, "collection_date", None) or None

    region_and_locality = sample_data.get("region_and_locality") or "unknown"

    country_or_sea = sample_data.get("country_or_sea") or "unknown"
    habitat = sample_data.get("habitat") or "unknown"
    collection_date_val = sample_data.get("date_of_collection") or sample_data.get(
        "collection_date"
    )
    collected_by = sample_data.get("collected_by") or "unknown"
    collecting_institution = sample_data.get("collecting_institution") or "unknown"

    sample_kwargs = dict(
        id=sample_id,
        taxon_id=taxon_id,
        bpa_sample_id=bpa_sample_id,
        specimen_id=sample_data.get("specimen_id"),
        specimen_id_description=sample_data.get("specimen_id_description"),
        identified_by=sample_data.get("identified_by"),
        specimen_custodian=sample_data.get("specimen_custodian"),
        sample_custodian=sample_data.get("sample_custodian"),
        lifestage=lifestage,
        sex=sex,
        organism_part=organism_part,
        region_and_locality=region_and_locality,
        state_or_region=sample_data.get("state_or_region"),
        country_or_sea=country_or_sea,
        indigenous_location=sample_data.get("indigenous_location"),
        habitat=habitat,
        collection_method=sample_data.get("description_of_collection_method")
        or sample_data.get("collection_method"),
        collected_by=collected_by,
        collecting_institution=collecting_institution,
        collection_date=collection_date_val,
        collection_permit=sample_data.get("collection_permit"),
        data_context=sample_data.get("data_context"),
        bioplatforms_project_id=sample_data.get("bioplatforms_project_id"),
        title=sample_data.get("title"),
        sample_same_as=sample_data.get("sample_same_as"),
        sample_derived_from=sample_data.get("sample_derived_from"),
        specimen_voucher=sample_data.get("specimen_voucher"),
        tolid=sample_data.get("tolid"),
        preservation_method=sample_data.get("preservation_method"),
        preservation_temperature=sample_data.get("preservation_temperature"),
        project_name=sample_data.get("project_name"),
        biosample_accession=sample_data.get("biosample_accession"),
        latitude=to_float(sample_data.get("latitude")),
        longitude=to_float(sample_data.get("longitude")),
        elevation=to_float(sample_data.get("elevation")),
        depth=to_float(sample_data.get("depth")),
        # Parent-child relationship fields
        derived_from_sample_id=derived_from_sample_id,
        kind=kind,
        extensions=sample_data.get("extensions"),
    )

    # Only set these if provided (DB has server defaults for NOT NULL)
    if sample_data.get("collected_by"):
        sample_kwargs["collected_by"] = sample_data.get("collected_by")
    if sample_data.get("collector_institute") or sample_data.get("collecting_institution"):
        sample_kwargs["collecting_institution"] = sample_data.get(
            "collector_institute"
        ) or sample_data.get("collecting_institution")

    sample = Sample(**sample_kwargs)

    # Create prepared_payload based on the mapping
    prepared_payload = {}
    if ena_atol_map:
        sample_mapping = ena_atol_map.get("sample", {})
        for ena_key, atol_key in sample_mapping.items():
            if atol_key in sample_data:
                prepared_payload[ena_key] = sample_data[atol_key]

    # Get project_id for this organism
    project_id = _get_genomic_data_project_id(db, taxon_id)

    # Create sample_submission record
    sample_submission = SampleSubmission(
        id=uuid.uuid4(),
        sample_id=sample_id,
        authority="ENA",
        entity_type_const="sample",
        prepared_payload=prepared_payload,
        project_id=project_id,
    )

    return sample, sample_submission


@router.post("/bulk-import-specimens", response_model=BulkImportResponse)
@policy("samples:bulk_import")
def bulk_import_specimen_samples(
    *,
    db: Session = Depends(get_db),
    samples_data: Dict[str, Dict[str, Any]],
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Bulk import specimen samples (kind='specimen').

    Expected format: Dictionary keyed by sample_key (a concat of taxon_id and specimen_id).
    Each sample must have taxon_id and specimen_id.
    Enforces uniqueness constraint: one specimen per (taxon_id, specimen_id).
    """
    # Load the ENA-ATOL mapping file
    ena_atol_map_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        "config",
        "ena-atol-map.json",
    )
    with open(ena_atol_map_path, "r") as f:
        ena_atol_map = json.load(f)

    created_count = 0
    skipped_count = 0
    errors = []

    for sample_key, sample_data in samples_data.items():
        try:
            # Get organism reference
            taxon_id = sample_data.get("taxon_id")
            if taxon_id is None:
                errors.append(f"{sample_key}: Missing taxon_id")
                skipped_count += 1
                continue

            organism = db.query(Organism).filter(Organism.taxon_id == int(taxon_id)).first()
            if not organism:
                errors.append(f"{sample_key}: Organism not found with taxon_id '{taxon_id}'")
                skipped_count += 1
                continue

            organism_taxon_id = _organism_taxon_id(organism)

            # Validate specimen_id is present
            specimen_id = sample_data.get("specimen_id")
            if not specimen_id:
                errors.append(f"{sample_key}: specimen_id is required for specimen samples")
                skipped_count += 1
                continue

            # Check for duplicate specimen
            existing_specimen = (
                db.query(Sample)
                .filter(
                    Sample.taxon_id == organism_taxon_id,
                    Sample.specimen_id == specimen_id,
                    Sample.kind == SampleKind.SPECIMEN,
                )
                .first()
            )
            if existing_specimen:
                errors.append(
                    f"{sample_key}: Specimen already exists for taxon_id '{organism_taxon_id}' "
                    f"and specimen_id '{specimen_id}'"
                )
                skipped_count += 1
                continue
            sample_data["organism_part"] = "WHOLE ORGANISM"

            # Create specimen sample (bpa_sample_id is optional for specimens)
            sample, sample_submission = _create_sample_with_submission(
                db=db,
                bpa_sample_id=sample_data.get("bpa_sample_id"),  # Optional for specimens
                sample_data=sample_data,
                taxon_id=organism_taxon_id,
                kind=SampleKind.SPECIMEN,
                derived_from_sample_id=None,
                ena_atol_map=ena_atol_map,
            )

            db.add(sample)
            db.add(sample_submission)
            db.commit()
            created_count += 1

        except Exception as e:
            errors.append(f"{sample_key}: {str(e)}")
            db.rollback()
            skipped_count += 1

    message = f"Specimen import complete. Created: {created_count}, Skipped: {skipped_count}"

    return {
        "created_count": created_count,
        "skipped_count": skipped_count,
        "message": message,
        "errors": errors if errors else None,  # Include all errors
    }


@router.post("/bulk-import-derived", response_model=BulkImportResponse)
@policy("samples:bulk_import")
def bulk_import_derived_samples(
    *,
    db: Session = Depends(get_db),
    samples_data: Dict[str, Dict[str, Any]],
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Bulk import derived samples (kind='derived').

    Expected format: Dictionary keyed by bpa_sample_id.
    Each sample must have:
    - taxon_id (to find organism)
    - specimen_id (to lookup parent specimen sample)

    The parent specimen is looked up by (taxon_id, specimen_id) or (taxon_id, specimen_id).
    """
    # Load the ENA-ATOL mapping file
    ena_atol_map_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        "config",
        "ena-atol-map.json",
    )
    with open(ena_atol_map_path, "r") as f:
        ena_atol_map = json.load(f)

    created_count = 0
    skipped_count = 0
    errors = []

    for sample_key, sample_data in samples_data.items():
        try:
            # Derived samples MUST have bpa_sample_id
            bpa_sample_id = sample_data.get("bpa_sample_id")
            if not bpa_sample_id:
                errors.append(f"{sample_key}: bpa_sample_id is required for derived samples")
                skipped_count += 1
                continue

            # Check if sample already exists by bpa_sample_id
            existing = db.query(Sample).filter(Sample.bpa_sample_id == bpa_sample_id).first()
            if existing:
                skipped_count += 1
                continue

            taxon_id = sample_data.get("taxon_id")
            organism = None
            if taxon_id is not None:
                organism = db.query(Organism).filter(Organism.taxon_id == int(taxon_id)).first()

            if not organism:
                errors.append(f"{sample_key}: Organism not found (provide taxon_id)")
                skipped_count += 1
                continue

            organism_taxon_id = _organism_taxon_id(organism)

            # Validate specimen_id is present (needed to find parent)
            specimen_id = sample_data.get("specimen_id")
            if not specimen_id:
                errors.append(f"{sample_key}: specimen_id is required to lookup parent specimen")
                skipped_count += 1
                continue

            # Lookup parent specimen by (taxon_id, specimen_id)
            parent_specimen = (
                db.query(Sample)
                .filter(
                    Sample.taxon_id == organism_taxon_id,
                    Sample.specimen_id == specimen_id,
                    Sample.kind == SampleKind.SPECIMEN,
                )
                .first()
            )

            if not parent_specimen:
                errors.append(
                    f"{sample_key}: Parent specimen not found for taxon_id '{organism_taxon_id}' "
                    f"and specimen_id '{specimen_id}'"
                )
                skipped_count += 1
                continue

            # Create derived sample
            sample, sample_submission = _create_sample_with_submission(
                db=db,
                bpa_sample_id=bpa_sample_id,
                sample_data=sample_data,
                taxon_id=organism_taxon_id,
                kind=SampleKind.DERIVED,
                derived_from_sample_id=parent_specimen.id,
                ena_atol_map=ena_atol_map,
            )

            db.add(sample)
            db.add(sample_submission)
            db.commit()
            created_count += 1

        except Exception as e:
            errors.append(f"{sample_key}: {str(e)}")
            db.rollback()
            skipped_count += 1

    message = f"Derived sample import complete. Created: {created_count}, Skipped: {skipped_count}"

    return {
        "created_count": created_count,
        "skipped_count": skipped_count,
        "message": message,
        "errors": errors if errors else None,  # Include all errors
    }


@router.get("/{sample_id}/prepared-payload", response_model=SubmissionJsonResponse)
@policy("samples:read_sensitive")
def get_sample_prepared_payload(
    *,
    db: Session = Depends(get_db),
    sample_id: UUID,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get prepared_payload for a specific sample.
    """
    sample_submission = (
        db.query(SampleSubmission).filter(SampleSubmission.sample_id == sample_id).first()
    )
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
@policy("samples:update")
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
    try:
        sample = db.query(Sample).filter(Sample.id == sample_id).first()
        if not sample:
            raise HTTPException(status_code=404, detail="Sample not found")

        sample_data = sample_in.model_dump(exclude_unset=True)
        prepared_payload = _build_sample_prepared_payload(sample_data)
        sample_submission = (
            db.query(SampleSubmission)
            .filter(SampleSubmission.sample_id == sample_id)
            .order_by(SampleSubmission.updated_at.desc())
            .first()
        )
        new_sample_submission = None
        latest_sample_submission = {}
        if not sample_submission:
            project_id = _get_genomic_data_project_id(db, sample.taxon_id)
            new_sample_submission = SampleSubmission(
                sample_id=sample_id,
                authority="ENA",
                entity_type_const="sample",
                prepared_payload=prepared_payload,
                status="draft",
                project_id=project_id,
            )
            db.add(new_sample_submission)
        else:
            latest_sample_submission = sample_submission

            if latest_sample_submission.status == "submitting":
                raise HTTPException(
                    status_code=404,
                    detail=f"Sample with id: {sample_id} is currently being submitted to ENA and could not be updated. Please try again later.",
                )
            elif (
                latest_sample_submission.status == "rejected"
                or sample_submission.status == "replaced"
            ):
                # leave the old record for logs and create a new record
                # retain accessions if they exist (accessions may not exist if status is 'rejected' and the sample has not successfully been submitted in the past)
                project_id = _get_genomic_data_project_id(db, sample.taxon_id)
                new_sample_submission = SampleSubmission(
                    sample_id=sample_id,
                    authority=sample_submission.authority,
                    entity_type_const="sample",
                    prepared_payload=prepared_payload,
                    response_payload=None,
                    accession=sample_submission.accession,
                    biosample_accession=sample_submission.biosample_accession,
                    status="draft",
                    project_id=project_id,
                )
                db.add(new_sample_submission)

            elif latest_sample_submission.status == "accepted":
                # change old record's status to "replaced" and create a new record
                # retain accessions
                setattr(latest_sample_submission, "status", "replaced")
                db.add(latest_sample_submission)
                project_id = _get_genomic_data_project_id(db, sample.taxon_id)
                new_sample_submission = SampleSubmission(
                    sample_id=sample_id,
                    authority=sample_submission.authority,
                    entity_type_const="sample",
                    prepared_payload=prepared_payload,
                    response_payload=None,
                    accession=sample_submission.accession,
                    biosample_accession=sample_submission.biosample_accession,
                    status="draft",
                    project_id=project_id,
                )
                db.add(new_sample_submission)
            elif (
                latest_sample_submission.status == "draft"
                or latest_sample_submission.status == "ready"
            ):
                # update the existing record, since it has not yet been submitted to ENA (set status = 'draft')
                setattr(latest_sample_submission, "prepared_payload", prepared_payload)
                setattr(latest_sample_submission, "status", "draft")
                db.add(latest_sample_submission)

        target_kind = SampleKind(sample_data["kind"]) if "kind" in sample_data else sample.kind
        target_taxon_id = sample_data.get("taxon_id", sample.taxon_id)
        target_specimen_id = sample_data.get("specimen_id", sample.specimen_id)
        target_parent_id = sample_data.get("derived_from_sample_id", sample.derived_from_sample_id)
        _validate_sample_lineage(
            db,
            sample_id=sample.id,
            taxon_id=target_taxon_id,
            kind=target_kind,
            specimen_id=target_specimen_id,
            derived_from_sample_id=target_parent_id,
        )

        for field, value in sample_data.items():
            if field not in _SAMPLE_MUTABLE_FIELDS:
                continue
            if field in _SAMPLE_NUMERIC_FIELDS:
                value = to_float(value)
            elif field == "kind" and value is not None:
                value = SampleKind(value)
            elif field in _SAMPLE_REQUIRED_TEXT_DEFAULTS and value in (None, ""):
                value = _SAMPLE_REQUIRED_TEXT_DEFAULTS[field]
            setattr(sample, field, value)

        db.add(sample)
        db.commit()
        db.refresh(sample)
        return sample
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        print(f"Error updating sample with sample_id: {sample_id}")
        print(e)
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update sample")


@router.delete("/{sample_id}", response_model=SampleSchema)
@policy("samples:delete")
def delete_sample(
    *,
    db: Session = Depends(get_db),
    sample_id: UUID,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Delete a sample.
    """
    sample = db.query(Sample).filter(Sample.id == sample_id).first()
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found")

    db.delete(sample)
    db.commit()
    return sample


# Sample Fetched endpoints have been removed as they are no longer in the schema


@router.post("/bulk-import", response_model=BulkImportResponse)
@policy("samples:bulk_import")
def bulk_import_samples(
    *,
    db: Session = Depends(get_db),
    samples_data: Dict[
        str, Dict[str, Any]
    ],  # Accept direct dictionary format from unique_samples.json
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Bulk import samples from a dictionary keyed by bpa_sample_id.

    The request body should directly match the format of the JSON file in data/unique_samples.json,
    which is a dictionary keyed by bpa_sample_id without a wrapping 'samples' key.
    """
    # Load the ENA-ATOL mapping file
    ena_atol_map_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        "config",
        "ena-atol-map.json",
    )
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
        taxon_id = None
        if "taxon_id" in sample_data:
            organism = (
                db.query(Organism).filter(Organism.taxon_id == sample_data["taxon_id"]).first()
            )
        else:
            print(f"Organism not found for sample {bpa_sample_id}, Skipping")
            skipped_count += 1
            continue
        if not organism:
            print(f"Organism not found with taxon_id {sample_data['taxon_id']}, Skipping")
            skipped_count += 1
            continue
        taxon_id = organism.taxon_id
        try:
            # Create new sample
            sample_id = uuid.uuid4()

            # Required fields with fallbacks
            lifestage = sample_data.get("lifestage") or "unknown"
            sex = sample_data.get("sex") or "unknown"
            organism_part = sample_data.get("organism_part") or "unknown"
            region_and_locality = sample_data.get("region_and_locality") or "unknown"
            country_or_sea = sample_data.get("country_or_sea") or "unknown"
            habitat = sample_data.get("habitat") or "unknown"
            collection_date_val = sample_data.get("collection_date") or "unknown"
            # Accept raw string and allow missing collection_date

            # Determine sample kind - default to specimen for bulk imports
            kind = sample_data.get("kind", SampleKind.SPECIMEN)
            if isinstance(kind, str):
                kind = SampleKind(kind)

            # Check for duplicate specimen: one specimen per (taxon_id, specimen_id)
            specimen_id_val = sample_data.get("specimen_id")
            if kind == SampleKind.SPECIMEN and specimen_id_val:
                existing_specimen = (
                    db.query(Sample)
                    .filter(
                        Sample.taxon_id == taxon_id,
                        Sample.specimen_id == specimen_id_val,
                        Sample.kind == SampleKind.SPECIMEN,
                    )
                    .first()
                )
                if existing_specimen:
                    print(
                        f"Specimen sample already exists for taxon_id '{taxon_id}' "
                        f"and specimen_id '{specimen_id_val}', skipping"
                    )
                    skipped_count += 1
                    continue

            sample_kwargs = dict(
                id=sample_id,
                taxon_id=taxon_id,
                bpa_sample_id=bpa_sample_id,
                specimen_id=sample_data.get("specimen_id"),
                identified_by=sample_data.get("identified_by"),
                specimen_custodian=sample_data.get("specimen_custodian"),
                sample_custodian=sample_data.get("sample_custodian"),
                lifestage=lifestage,
                sex=sex,
                organism_part=organism_part,
                region_and_locality=region_and_locality,
                country_or_sea=country_or_sea,
                habitat=habitat,
                collection_method=sample_data.get("description_of_collection_method")
                or sample_data.get("collection_method"),
                collection_date=collection_date_val,
                collection_permit=sample_data.get("collection_permit"),
                data_context=sample_data.get("data_context"),
                bioplatforms_project_id=sample_data.get("bioplatforms_project_id"),
                latitude=to_float(sample_data.get("latitude")),
                longitude=to_float(sample_data.get("longitude")),
                elevation=to_float(sample_data.get("elevation")),
                depth=to_float(sample_data.get("depth")),
                # Parent-child relationship fields
                derived_from_sample_id=sample_data.get("derived_from_sample_id"),
                kind=kind,
                extensions=sample_data.get("extensions"),
                # bpa_json=sample_data
            )
            if sample_data.get("collected_by"):
                sample_kwargs["collected_by"] = sample_data.get("collected_by")
            if sample_data.get("collector_institute") or sample_data.get("collecting_institution"):
                sample_kwargs["collecting_institution"] = sample_data.get(
                    "collector_institute"
                ) or sample_data.get("collecting_institution")

            sample = Sample(**sample_kwargs)
            db.add(sample)

            # Create prepared_payload based on the mapping
            prepared_payload = {}
            for ena_key, atol_key in sample_mapping.items():
                if atol_key in sample_data:
                    prepared_payload[ena_key] = sample_data[atol_key]

            # Get project_id for this organism
            project_id = _get_genomic_data_project_id(db, taxon_id)

            # Create sample_submission record
            sample_submission = SampleSubmission(
                id=uuid.uuid4(),
                sample_id=sample_id,
                authority="ENA",
                entity_type_const="sample",
                prepared_payload=prepared_payload,
                project_id=project_id,
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
        f"Created submission records: {created_submission_count}, Skipped: {skipped_count}",
    }


@router.get(
    "/submission/by-experiment/{bpa_package_id}", response_model=List[SampleSubmissionSchema]
)
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
            status_code=404, detail=f"Experiment with bpa_package_id {bpa_package_id} not found"
        )

    # Get the sample_id from the experiment
    if not experiment.sample_id:
        raise HTTPException(
            status_code=404,
            detail=f"Experiment with bpa_package_id {bpa_package_id} has no associated sample",
        )

    # Find the submission records for this sample
    submission_records = (
        db.query(SampleSubmission).filter(SampleSubmission.sample_id == experiment.sample_id).all()
    )

    if not submission_records:
        raise HTTPException(
            status_code=404,
            detail=f"No submission sample records found for experiment with bpa_package_id {bpa_package_id}",
        )

    return submission_records


@router.get("/{sample_id}/children", response_model=List[SampleSchema])
def get_sample_children(
    *,
    db: Session = Depends(get_db),
    sample_id: UUID,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get all derived samples (children) of a specimen sample.
    """
    # All users can read sample relationships
    sample = db.query(Sample).filter(Sample.id == sample_id).first()
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found")

    if sample.kind != SampleKind.SPECIMEN:
        raise HTTPException(status_code=400, detail="Only specimen samples can have children")

    children = db.query(Sample).filter(Sample.derived_from_sample_id == sample_id).all()
    return children


@router.get("/{sample_id}/parent", response_model=SampleSchema)
def get_sample_parent(
    *,
    db: Session = Depends(get_db),
    sample_id: UUID,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get the parent specimen sample of a derived sample.
    """
    # All users can read sample relationships
    sample = db.query(Sample).filter(Sample.id == sample_id).first()
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found")

    if sample.kind != SampleKind.DERIVED:
        raise HTTPException(status_code=400, detail="Only derived samples have a parent")

    if not sample.derived_from_sample_id:
        raise HTTPException(status_code=404, detail="Parent sample not found")

    parent = db.query(Sample).filter(Sample.id == sample.derived_from_sample_id).first()
    if not parent:
        raise HTTPException(status_code=404, detail="Parent sample not found")

    return parent

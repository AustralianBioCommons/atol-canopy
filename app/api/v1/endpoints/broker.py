from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.dependencies import get_db, has_role
from app.models.sample import Sample, SampleSubmission
from app.models.accession_registry import AccessionRegistry
from sqlalchemy.dialects.postgresql import insert
from app.models.experiment import Experiment, ExperimentSubmission
from app.models.read import Read, ReadSubmission

router = APIRouter(dependencies=[Depends(has_role(["broker"]))])


# ---------- Pydantic models for request/response ----------
class ClaimedEntity(BaseModel):
    id: UUID
    status: Optional[str] = None
    prepared_payload: Optional[Dict[str, Any]] = None
    accession: Optional[str] = None


class ClaimResponse(BaseModel):
    batch_id: UUID
    organism_key: str
    samples: List[ClaimedEntity] = Field(default_factory=list)
    experiments: List[ClaimedEntity] = Field(default_factory=list)
    reads: List[ClaimedEntity] = Field(default_factory=list)


class ReportItem(BaseModel):
    id: UUID
    status: str
    response_payload: Optional[Dict[str, Any]] = None
    accession: Optional[str] = None
    submitted_at: Optional[datetime] = None
    biosample_accession: Optional[str] = None
    project_accession: Optional[str] = None
    sample_accession: Optional[str] = None
    experiment_accession: Optional[str] = None


class ReportRequest(BaseModel):
    batch_id: Optional[UUID] = None
    samples: List[ReportItem] = Field(default_factory=list)
    experiments: List[ReportItem] = Field(default_factory=list)
    reads: List[ReportItem] = Field(default_factory=list)


class ReportResult(BaseModel):
    updated_counts: Dict[str, int]


# ---------- Endpoints ----------
@router.post("/organisms/{organism_key}/claim", response_model=ClaimResponse)
def claim_drafts_for_organism(
    *,
    organism_key: str = Path(..., description="Organism grouping_key"),
    per_type_limit: int = Query(100, ge=1, le=1000, description="Max items per type to claim"),
    db: Session = Depends(get_db),
) -> ClaimResponse:
    """Claim latest draft SampleSubmissions for an organism and mark them 'submitting'.
    This acts as a short lease to prevent concurrent edits.
    """
    batch_id = uuid4()

    claimed_samples: List[ClaimedEntity] = []
    claimed_experiments: List[ClaimedEntity] = []
    claimed_reads: List[ClaimedEntity] = []
    now = datetime.now(timezone.utc)
    ttl = timedelta(minutes=15)

    # Latest draft per sample_id using window function (avoid DISTINCT with FOR UPDATE)
    sample_rank_subq = (
        db.query(
            SampleSubmission.id.label("id"),
            func.row_number()
                .over(
                    partition_by=SampleSubmission.sample_id,
                    order_by=SampleSubmission.created_at.desc(),
                )
                .label("rn"),
        )
        .join(Sample, SampleSubmission.sample_id == Sample.id)
        .filter(Sample.organism_key == organism_key, SampleSubmission.status == "draft")
    ).subquery()

    sample_ids_subq = (
        db.query(sample_rank_subq.c.id)
        .filter(sample_rank_subq.c.rn == 1)
        .limit(per_type_limit)
    ).subquery()

    # Acquire row locks and mark as submitting
    sample_rows = (
        db.query(SampleSubmission)
        .filter(SampleSubmission.id.in_(db.query(sample_ids_subq.c.id)))
        .filter(SampleSubmission.status == "draft")
        .with_for_update(skip_locked=True)
        .all()
    )
    for row in sample_rows:
        row.status = "submitting"
        row.batch_id = batch_id
        row.lock_acquired_at = now
        row.lock_expires_at = now + ttl
    db.commit()

    for row in sample_rows:
        claimed_samples.append(
            ClaimedEntity(
                id=row.id,
                status=row.status,
                prepared_payload=row.prepared_payload,
                accession=row.accession,
            )
        )

    # Latest draft ExperimentSubmission per experiment_id under this organism (window function)
    exp_rank_subq = (
        db.query(
            ExperimentSubmission.id.label("id"),
            func.row_number()
                .over(
                    partition_by=ExperimentSubmission.experiment_id,
                    order_by=ExperimentSubmission.created_at.desc(),
                )
                .label("rn"),
        )
        .join(Experiment, ExperimentSubmission.experiment_id == Experiment.id)
        .join(Sample, Experiment.sample_id == Sample.id)
        .filter(Sample.organism_key == organism_key, ExperimentSubmission.status == "draft")
    ).subquery()

    exp_ids_subq = (
        db.query(exp_rank_subq.c.id)
        .filter(exp_rank_subq.c.rn == 1)
        .limit(per_type_limit)
    ).subquery()

    exp_rows = (
        db.query(ExperimentSubmission)
        .filter(ExperimentSubmission.id.in_(db.query(exp_ids_subq.c.id)))
        .filter(ExperimentSubmission.status == "draft")
        .with_for_update(skip_locked=True)
        .all()
    )
    for row in exp_rows:
        row.status = "submitting"
        row.batch_id = batch_id
        row.lock_acquired_at = now
        row.lock_expires_at = now + ttl
    db.commit()

    for row in exp_rows:
        claimed_experiments.append(
            ClaimedEntity(
                id=row.id,
                status=row.status,
                prepared_payload=row.prepared_payload,
                accession=row.accession,
            )
        )

    # Latest draft ReadSubmission per read_id under this organism (window function)
    read_rank_subq = (
        db.query(
            ReadSubmission.id.label("id"),
            func.row_number()
                .over(
                    partition_by=ReadSubmission.read_id,
                    order_by=ReadSubmission.created_at.desc(),
                )
                .label("rn"),
        )
        .join(Read, ReadSubmission.read_id == Read.id)
        .join(Experiment, Read.experiment_id == Experiment.id)
        .join(Sample, Experiment.sample_id == Sample.id)
        .filter(Sample.organism_key == organism_key, ReadSubmission.status == "draft")
    ).subquery()

    read_ids_subq = (
        db.query(read_rank_subq.c.id)
        .filter(read_rank_subq.c.rn == 1)
        .limit(per_type_limit)
    ).subquery()

    read_rows = (
        db.query(ReadSubmission)
        .filter(ReadSubmission.id.in_(db.query(read_ids_subq.c.id)))
        .filter(ReadSubmission.status == "draft")
        .with_for_update(skip_locked=True)
        .all()
    )
    for row in read_rows:
        row.status = "submitting"
        row.batch_id = batch_id
        row.lock_acquired_at = now
        row.lock_expires_at = now + ttl
    db.commit()

    for row in read_rows:
        claimed_reads.append(
            ClaimedEntity(
                id=row.id,
                status=row.status,
                prepared_payload=row.prepared_payload,
                accession=row.accession,
            )
        )

    return ClaimResponse(
        batch_id=batch_id,
        organism_key=organism_key,
        samples=claimed_samples,
        experiments=claimed_experiments,
        reads=claimed_reads,
    )


@router.post("/batches/{batch_id}/report", response_model=ReportResult)
def report_results(
    *,
    batch_id: UUID,
    payload: ReportRequest,
    db: Session = Depends(get_db),
) -> ReportResult:
    """Apply broker results: update statuses/payloads and register accessions (samples only for now)."""
    updated_samples = 0
    updated_experiments = 0
    updated_reads = 0

    # Process SampleSubmission updates
    for item in payload.samples:
        sub = db.query(SampleSubmission).filter(SampleSubmission.id == item.id).first()
        if not sub:
            raise HTTPException(status_code=404, detail=f"SampleSubmission {item.id} not found")

        # Only allow updating from 'submitting' lease state
        if sub.status != "submitting":
            raise HTTPException(status_code=409, detail=f"SampleSubmission {item.id} not in 'submitting' state")
        # If batch tracking is active, enforce match
        if sub.batch_id and sub.batch_id != batch_id:
            raise HTTPException(status_code=409, detail=f"SampleSubmission {item.id} belongs to different batch")

        # Apply updates
        sub.status = item.status
        sub.response_payload = item.response_payload
        if item.accession:
            sub.accession = item.accession
        if item.submitted_at:
            if hasattr(sub, "submitted_at"):
                sub.submitted_at = item.submitted_at

        db.add(sub)
        db.flush()

        # Register accession if present
        if item.accession and sub.sample_id is not None:
            stmt = insert(AccessionRegistry).values(
                authority=sub.authority or "ENA",
                accession=item.accession,
                entity_type="sample",
                entity_id=sub.sample_id,
                accepted_at=item.submitted_at or datetime.now(timezone.utc),
            )
            # On conflict by (authority, accession) or (authority, entity_type, entity_id), do nothing
            stmt = stmt.on_conflict_do_nothing(index_elements=[AccessionRegistry.accession])
            db.execute(stmt)

        # Clear lease on finalize (anything other than submitting)
        if item.status != "submitting":
            sub.batch_id = None
            sub.lock_acquired_at = None
            sub.lock_expires_at = None

        updated_samples += 1

    # Process ExperimentSubmission updates
    for item in payload.experiments:
        sub = db.query(ExperimentSubmission).filter(ExperimentSubmission.id == item.id).first()
        if not sub:
            raise HTTPException(status_code=404, detail=f"ExperimentSubmission {item.id} not found")

        if sub.status != "submitting":
            raise HTTPException(status_code=409, detail=f"ExperimentSubmission {item.id} not in 'submitting' state")
        if sub.batch_id and sub.batch_id != batch_id:
            raise HTTPException(status_code=409, detail=f"ExperimentSubmission {item.id} belongs to different batch")

        sub.status = item.status
        sub.response_payload = item.response_payload
        if item.accession:
            sub.accession = item.accession
        # upstream accessions
        if item.project_accession:
            sub.project_accession = item.project_accession
        if item.sample_accession:
            sub.sample_accession = item.sample_accession
        if item.submitted_at and hasattr(sub, "submitted_at"):
            sub.submitted_at = item.submitted_at

        db.add(sub)
        db.flush()

        if item.accession and sub.experiment_id is not None:
            stmt = insert(AccessionRegistry).values(
                authority=sub.authority or "ENA",
                accession=item.accession,
                entity_type="experiment",
                entity_id=sub.experiment_id,
                accepted_at=item.submitted_at or datetime.now(timezone.utc),
            )
            stmt = stmt.on_conflict_do_nothing(index_elements=[AccessionRegistry.accession])
            db.execute(stmt)

        if item.status != "submitting":
            sub.batch_id = None
            sub.lock_acquired_at = None
            sub.lock_expires_at = None

        updated_experiments += 1

    # Process ReadSubmission updates
    for item in payload.reads:
        sub = db.query(ReadSubmission).filter(ReadSubmission.id == item.id).first()
        if not sub:
            raise HTTPException(status_code=404, detail=f"ReadSubmission {item.id} not found")

        if sub.status != "submitting":
            raise HTTPException(status_code=409, detail=f"ReadSubmission {item.id} not in 'submitting' state")
        if sub.batch_id and sub.batch_id != batch_id:
            raise HTTPException(status_code=409, detail=f"ReadSubmission {item.id} belongs to different batch")

        sub.status = item.status
        sub.response_payload = item.response_payload
        if item.accession:
            sub.accession = item.accession
        # upstream experiment accession if provided
        if item.experiment_accession:
            sub.experiment_accession = item.experiment_accession

        db.add(sub)
        db.flush()

        if item.accession and sub.read_id is not None:
            stmt = insert(AccessionRegistry).values(
                authority=sub.authority or "ENA",
                accession=item.accession,
                entity_type="read",
                entity_id=sub.read_id,
                accepted_at=item.submitted_at or datetime.now(timezone.utc),
            )
            stmt = stmt.on_conflict_do_nothing(index_elements=[AccessionRegistry.accession])
            db.execute(stmt)

        if item.status != "submitting":
            sub.batch_id = None
            sub.lock_acquired_at = None
            sub.lock_expires_at = None

        updated_reads += 1

    db.commit()

    return ReportResult(
        updated_counts={
            "samples": updated_samples,
            "experiments": updated_experiments,
            "reads": updated_reads,
        }
    )

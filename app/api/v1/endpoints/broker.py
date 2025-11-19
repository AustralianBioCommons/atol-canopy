from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Body
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.dependencies import get_db, has_role
from app.models.sample import Sample, SampleSubmission
from app.models.accession_registry import AccessionRegistry
from sqlalchemy.dialects.postgresql import insert
from app.models.experiment import Experiment, ExperimentSubmission
from app.models.read import Read, ReadSubmission
from app.models.broker import SubmissionBatch, SubmissionAttempt

router = APIRouter(dependencies=[Depends(has_role(["broker"]))])


# ---------- Pydantic models for request/response ----------
class ClaimedEntity(BaseModel):
    id: UUID
    status: Optional[str] = None
    prepared_payload: Optional[Dict[str, Any]] = None
    accession: Optional[str] = None


class ClaimResponse(BaseModel):
    batch_id: UUID
    attempt_id: UUID
    organism_key: str
    samples: List[ClaimedEntity] = Field(default_factory=list)
    experiments: List[ClaimedEntity] = Field(default_factory=list)
    reads: List[ClaimedEntity] = Field(default_factory=list)


class ClaimRequest(BaseModel):
    # Optional explicit selection by submission IDs; if provided, organism_key is not enforced
    sample_submission_ids: Optional[List[UUID]] = None
    experiment_submission_ids: Optional[List[UUID]] = None
    read_submission_ids: Optional[List[UUID]] = None
    # option to override lease, in mins
    lease_duration_minutes: Optional[int] = Field(default=None, ge=1, le=180)


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
    attempt_id: Optional[UUID] = None
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
    payload: Optional[ClaimRequest] = Body(default=None),
    db: Session = Depends(get_db),
) -> ClaimResponse:
    """Claim latest draft SampleSubmissions for an organism and mark them 'submitting'.
    This acts as a short lease to prevent concurrent edits.
    """
    # Create a batch and an attempt for this claim
    batch = SubmissionBatch(organism_key=organism_key, status="processing")
    db.add(batch)
    db.flush()
    lease_minutes = 15
    if payload and payload.lease_duration_minutes:
        lease_minutes = payload.lease_duration_minutes
    ttl = timedelta(minutes=lease_minutes)
    now = datetime.now()
    attempt = SubmissionAttempt(
        batch_id=batch.id,
        status="processing",
        lock_acquired_at=now,
        lock_expires_at=now + ttl,
    )
    db.add(attempt)
    db.flush()
    batch_id = batch.id
    attempt_id = attempt.id

    claimed_samples: List[ClaimedEntity] = []
    claimed_experiments: List[ClaimedEntity] = []
    claimed_reads: List[ClaimedEntity] = []

    # Choose sample rows by explicit IDs (if provided) else by organism/limit
    if payload and payload.sample_submission_ids:
        sample_rows = (
            db.query(SampleSubmission)
            .filter(SampleSubmission.id.in_(payload.sample_submission_ids))
            .filter(SampleSubmission.status == "draft")
            .with_for_update(skip_locked=True)
            .all()
        )
    else:
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
        row.attempt_id = attempt_id
        row.lock_acquired_at = now
        row.lock_expires_at = attempt.lock_expires_at
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

    # Choose experiment rows by explicit IDs (if provided) else by organism/limit
    if payload and payload.experiment_submission_ids:
        exp_rows = (
            db.query(ExperimentSubmission)
            .filter(ExperimentSubmission.id.in_(payload.experiment_submission_ids))
            .filter(ExperimentSubmission.status == "draft")
            .with_for_update(skip_locked=True)
            .all()
        )
    else:
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
        row.attempt_id = attempt_id
        row.lock_acquired_at = now
        row.lock_expires_at = attempt.lock_expires_at
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

    # Choose read rows by explicit IDs (if provided) else by organism/limit
    if payload and payload.read_submission_ids:
        read_rows = (
            db.query(ReadSubmission)
            .filter(ReadSubmission.id.in_(payload.read_submission_ids))
            .filter(ReadSubmission.status == "draft")
            .with_for_update(skip_locked=True)
            .all()
        )
    else:
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
        row.attempt_id = attempt_id
        row.lock_acquired_at = now
        row.lock_expires_at = attempt.lock_expires_at
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
        attempt_id=attempt_id,
        organism_key=organism_key,
        samples=claimed_samples,
        experiments=claimed_experiments,
        reads=claimed_reads,
    )

@router.post("/attempts/{attempt_id}/lease/renew")
def renew_attempt_lease(
    *,
    attempt_id: UUID,
    extend_minutes: int = Query(15, ge=1, le=180),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Extend the lease for an attempt and its claimed items."""
    attempt = db.query(SubmissionAttempt).filter(SubmissionAttempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")

    now = datetime.now()
    current_exp = attempt.lock_expires_at or now
    new_exp = (current_exp if current_exp > now else now) + timedelta(minutes=extend_minutes)
    attempt.lock_expires_at = new_exp
    db.add(attempt)

    # Propagate to items in submitting state
    for sub in db.query(SampleSubmission).filter(SampleSubmission.attempt_id == attempt_id, SampleSubmission.status == "submitting").all():
        sub.lock_expires_at = new_exp
    for sub in db.query(ExperimentSubmission).filter(ExperimentSubmission.attempt_id == attempt_id, ExperimentSubmission.status == "submitting").all():
        sub.lock_expires_at = new_exp
    for sub in db.query(ReadSubmission).filter(ReadSubmission.attempt_id == attempt_id, ReadSubmission.status == "submitting").all():
        sub.lock_expires_at = new_exp

    db.commit()
    return {"attempt_id": str(attempt_id), "lock_expires_at": new_exp.isoformat()}


@router.post("/attempts/{attempt_id}/finalize")
def finalize_attempt(
    *,
    attempt_id: UUID,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Finalize an attempt: release any remaining 'submitting' items back to 'draft' and close the attempt."""
    attempt = db.query(SubmissionAttempt).filter(SubmissionAttempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")

    released = {"samples": 0, "experiments": 0, "reads": 0}

    # Samples
    sample_rows = db.query(SampleSubmission).filter(SampleSubmission.attempt_id == attempt_id, SampleSubmission.status == "submitting").all()
    for sub in sample_rows:
        sub.status = "draft"
        sub.batch_id = None
        sub.attempt_id = None
        sub.lock_acquired_at = None
        sub.lock_expires_at = None
        released["samples"] += 1

    # Experiments
    exp_rows = db.query(ExperimentSubmission).filter(ExperimentSubmission.attempt_id == attempt_id, ExperimentSubmission.status == "submitting").all()
    for sub in exp_rows:
        sub.status = "draft"
        sub.batch_id = None
        sub.attempt_id = None
        sub.lock_acquired_at = None
        sub.lock_expires_at = None
        released["experiments"] += 1

    # Reads
    read_rows = db.query(ReadSubmission).filter(ReadSubmission.attempt_id == attempt_id, ReadSubmission.status == "submitting").all()
    for sub in read_rows:
        sub.status = "draft"
        sub.batch_id = None
        sub.attempt_id = None
        sub.lock_acquired_at = None
        sub.lock_expires_at = None
        released["reads"] += 1

    attempt.status = "complete"
    db.add(attempt)
    db.commit()

    return {"attempt_id": str(attempt_id), "released": released, "status": attempt.status}


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
    provided_attempt_id = payload.attempt_id

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
        if provided_attempt_id is not None and sub.attempt_id != provided_attempt_id:
            raise HTTPException(status_code=409, detail=f"SampleSubmission {item.id} belongs to different attempt")

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
                accepted_at=item.submitted_at or datetime.now(),
            )
            # On conflict by (authority, accession) or (authority, entity_type, entity_id), do nothing
            stmt = stmt.on_conflict_do_nothing(index_elements=[AccessionRegistry.accession])
            db.execute(stmt)

        # Clear lease on finalize (anything other than submitting)
        if item.status != "submitting":
            sub.batch_id = None
            sub.attempt_id = None
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
        if provided_attempt_id is not None and sub.attempt_id != provided_attempt_id:
            raise HTTPException(status_code=409, detail=f"ExperimentSubmission {item.id} belongs to different attempt")

        sub.status = item.status
        sub.response_payload = item.response_payload
        if item.accession:
            sub.accession = item.accession
        # Ensure upstream sample accession exists in registry BEFORE setting FK
        if item.sample_accession:
            stmt = insert(AccessionRegistry).values(
                authority=sub.authority or "ENA",
                accession=item.sample_accession,
                entity_type="sample",
                entity_id=sub.sample_id,
                accepted_at=item.submitted_at or datetime.now(),
            )
            stmt = stmt.on_conflict_do_nothing(index_elements=[AccessionRegistry.accession])
            db.execute(stmt)
            sub.sample_accession = item.sample_accession
        if item.project_accession:
            sub.project_accession = item.project_accession
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
                accepted_at=item.submitted_at or datetime.now(),
            )
            stmt = stmt.on_conflict_do_nothing(index_elements=[AccessionRegistry.accession])
            db.execute(stmt)

        if item.status != "submitting":
            sub.batch_id = None
            sub.attempt_id = None
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
        if provided_attempt_id is not None and sub.attempt_id != provided_attempt_id:
            raise HTTPException(status_code=409, detail=f"ReadSubmission {item.id} belongs to different attempt")

        sub.status = item.status
        sub.response_payload = item.response_payload
        if item.accession:
            sub.accession = item.accession
        # Ensure upstream experiment accession exists in registry BEFORE setting FK
        if item.experiment_accession:
            stmt = insert(AccessionRegistry).values(
                authority=sub.authority or "ENA",
                accession=item.experiment_accession,
                entity_type="experiment",
                entity_id=sub.experiment_id,
                accepted_at=item.submitted_at or datetime.now(),
            )
            stmt = stmt.on_conflict_do_nothing(index_elements=[AccessionRegistry.accession])
            db.execute(stmt)
            sub.experiment_accession = item.experiment_accession

        db.add(sub)
        db.flush()

        if item.accession and sub.read_id is not None:
            stmt = insert(AccessionRegistry).values(
                authority=sub.authority or "ENA",
                accession=item.accession,
                entity_type="read",
                entity_id=sub.read_id,
                accepted_at=item.submitted_at or datetime.now(),
            )
            stmt = stmt.on_conflict_do_nothing(index_elements=[AccessionRegistry.accession])
            db.execute(stmt)

        if item.status != "submitting":
            sub.batch_id = None
            sub.attempt_id = None
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

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Body
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.core.dependencies import get_db, has_role
from app.models.sample import Sample, SampleSubmission
from app.models.accession_registry import AccessionRegistry
from sqlalchemy.dialects.postgresql import insert
from app.models.experiment import Experiment, ExperimentSubmission
from app.models.read import Read, ReadSubmission
from app.models.broker import SubmissionAttempt, SubmissionEvent

router = APIRouter(dependencies=[Depends(has_role(["broker"]))])


# ---------- Pydantic models for request/response ----------
class ClaimedEntity(BaseModel):
    id: UUID
    status: Optional[str] = None
    prepared_payload: Optional[Dict[str, Any]] = None
    accession: Optional[str] = None
    # Derived relationship info for dependency resolution at client side
    relationships: Optional[Dict[str, Any]] = None


class ClaimResponse(BaseModel):
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
    # Create an attempt for this claim (attempt-only model)
    lease_minutes = 30
    if payload and payload.lease_duration_minutes:
        lease_minutes = payload.lease_duration_minutes
    ttl = timedelta(minutes=lease_minutes)
    now = datetime.now(timezone.utc)
    attempt = SubmissionAttempt(
        organism_key=organism_key,
        status="processing",
        lock_acquired_at=now,
        lock_expires_at=now + ttl,
    )
    db.add(attempt)
    db.flush()
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
        row.attempt_id = attempt_id
        row.lock_acquired_at = now
        row.lock_expires_at = attempt.lock_expires_at
        db.add(SubmissionEvent(attempt_id=attempt_id, entity_type="sample", submission_id=row.id, action="claimed"))
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
        row.attempt_id = attempt_id
        row.lock_acquired_at = now
        row.lock_expires_at = attempt.lock_expires_at
        db.add(SubmissionEvent(attempt_id=attempt_id, entity_type="experiment", submission_id=row.id, action="claimed"))
    db.commit()

    # Build relationships for experiments -> sample/sample_submission
    exp_ids = [r.experiment_id for r in exp_rows]
    exp_sample_pairs = (
        db.query(Experiment.id, Experiment.sample_id)
        .filter(Experiment.id.in_(exp_ids))
        .all()
        if exp_rows else []
    )
    sample_id_by_experiment_id: Dict[UUID, UUID] = {eid: sid for (eid, sid) in exp_sample_pairs}

    # Map of claimed sample submissions in this attempt: sample_id -> SampleSubmission row
    claimed_sample_by_sample_id: Dict[UUID, SampleSubmission] = {r.sample_id: r for r in sample_rows}

    # For experiments whose samples weren't claimed, fall back to latest accepted sample submission
    missing_sample_ids = [sid for sid in set(sample_id_by_experiment_id.values()) if sid not in claimed_sample_by_sample_id]
    accepted_sample_by_sample_id: Dict[UUID, SampleSubmission] = {}
    if missing_sample_ids:
        accepted_samples = (
            db.query(SampleSubmission)
            .filter(SampleSubmission.sample_id.in_(missing_sample_ids), SampleSubmission.status == "accepted")
            .all()
        )
        accepted_sample_by_sample_id = {r.sample_id: r for r in accepted_samples}

    for row in exp_rows:
        sid = sample_id_by_experiment_id.get(row.experiment_id)
        parent_ss = claimed_sample_by_sample_id.get(sid) or accepted_sample_by_sample_id.get(sid)
        relationships = {
            "sample_id": sid,
            "sample_submission_id": (parent_ss.id if parent_ss else None),
            "sample_accession": (parent_ss.accession if parent_ss else row.sample_accession if hasattr(row, "sample_accession") else None),
            "project_accession": (row.project_accession if hasattr(row, "project_accession") else None),
        }
        claimed_experiments.append(
            ClaimedEntity(
                id=row.id,
                status=row.status,
                prepared_payload=row.prepared_payload,
                accession=row.accession,
                relationships=relationships,
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
        row.attempt_id = attempt_id
        row.lock_acquired_at = now
        row.lock_expires_at = attempt.lock_expires_at
        db.add(SubmissionEvent(attempt_id=attempt_id, entity_type="read", submission_id=row.id, action="claimed"))
    db.commit()

    # Build relationships for reads -> experiment/experiment_submission
    read_exp_ids = [r.experiment_id for r in read_rows]
    # Map of claimed experiment submissions: experiment_id -> ExperimentSubmission row
    claimed_exp_by_experiment_id: Dict[UUID, ExperimentSubmission] = {r.experiment_id: r for r in exp_rows}

    # For reads whose experiments weren't claimed, fall back to latest accepted experiment submission
    missing_exp_ids = [eid for eid in set(read_exp_ids) if eid not in claimed_exp_by_experiment_id]
    accepted_exp_by_experiment_id: Dict[UUID, ExperimentSubmission] = {}
    if missing_exp_ids:
        accepted_exps = (
            db.query(ExperimentSubmission)
            .filter(ExperimentSubmission.experiment_id.in_(missing_exp_ids), ExperimentSubmission.status == "accepted")
            .all()
        )
        accepted_exp_by_experiment_id = {r.experiment_id: r for r in accepted_exps}

    for row in read_rows:
        exp_parent = claimed_exp_by_experiment_id.get(row.experiment_id) or accepted_exp_by_experiment_id.get(row.experiment_id)
        relationships = {
            "experiment_id": row.experiment_id,
            "experiment_submission_id": (exp_parent.id if exp_parent else None),
            "experiment_accession": (exp_parent.accession if exp_parent else row.experiment_accession if hasattr(row, "experiment_accession") else None),
        }
        claimed_reads.append(
            ClaimedEntity(
                id=row.id,
                status=row.status,
                prepared_payload=row.prepared_payload,
                accession=row.accession,
                relationships=relationships,
            )
        )

    return ClaimResponse(
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
        sub.attempt_id = None
        sub.lock_acquired_at = None
        sub.lock_expires_at = None
        db.add(SubmissionEvent(attempt_id=attempt_id, entity_type="sample", submission_id=sub.id, action="released"))
        released["samples"] += 1

    # Experiments
    exp_rows = db.query(ExperimentSubmission).filter(ExperimentSubmission.attempt_id == attempt_id, ExperimentSubmission.status == "submitting").all()
    for sub in exp_rows:
        sub.status = "draft"
        sub.attempt_id = None
        sub.lock_acquired_at = None
        sub.lock_expires_at = None
        db.add(SubmissionEvent(attempt_id=attempt_id, entity_type="experiment", submission_id=sub.id, action="released"))
        released["experiments"] += 1

    # Reads
    read_rows = db.query(ReadSubmission).filter(ReadSubmission.attempt_id == attempt_id, ReadSubmission.status == "submitting").all()
    for sub in read_rows:
        sub.status = "draft"
        sub.attempt_id = None
        sub.lock_acquired_at = None
        sub.lock_expires_at = None
        db.add(SubmissionEvent(attempt_id=attempt_id, entity_type="read", submission_id=sub.id, action="released"))
        released["reads"] += 1

    attempt.status = "complete"
    db.add(attempt)
    db.commit()

    return {"attempt_id": str(attempt_id), "released": released, "status": attempt.status}


@router.post("/attempts/{attempt_id}/report", response_model=ReportResult)
def report_results(
    *,
    attempt_id: UUID,
    payload: ReportRequest,
    db: Session = Depends(get_db),
) -> ReportResult:
    """Apply broker results: update statuses/payloads and register accessions (samples only for now)."""
    updated_samples = 0
    updated_experiments = 0
    updated_reads = 0
    provided_attempt_id = payload.attempt_id or attempt_id

    # Process SampleSubmission updates
    for item in payload.samples:
        sub = db.query(SampleSubmission).filter(SampleSubmission.id == item.id).first()
        if not sub:
            raise HTTPException(status_code=404, detail=f"SampleSubmission {item.id} not found")

        # Only allow updating from 'submitting' lease state
        if sub.status != "submitting":
            raise HTTPException(status_code=409, detail=f"SampleSubmission {item.id} not in 'submitting' state")
        # If batch tracking is active, enforce match
        if sub.attempt_id != provided_attempt_id:
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
                accepted_at=item.submitted_at or datetime.now(timezone.utc),
            )
            # On conflict by (authority, accession) or (authority, entity_type, entity_id), do nothing
            stmt = stmt.on_conflict_do_nothing(index_elements=[AccessionRegistry.accession])
            db.execute(stmt)

        # Clear lease on finalize (anything other than submitting)
        if item.status != "submitting":
            sub.attempt_id = None
            sub.lock_acquired_at = None
            sub.lock_expires_at = None
            sub.finalized_attempt_id = attempt_id
            # event
            action = "accepted" if item.status == "accepted" else ("rejected" if item.status == "rejected" else "released")
            db.add(SubmissionEvent(attempt_id=attempt_id, entity_type="sample", submission_id=sub.id, action=action, accession=item.accession, details=item.response_payload))

        updated_samples += 1

    # Process ExperimentSubmission updates
    for item in payload.experiments:
        sub = db.query(ExperimentSubmission).filter(ExperimentSubmission.id == item.id).first()
        if not sub:
            raise HTTPException(status_code=404, detail=f"ExperimentSubmission {item.id} not found")

        if sub.status != "submitting":
            raise HTTPException(status_code=409, detail=f"ExperimentSubmission {item.id} not in 'submitting' state")
        if sub.attempt_id != provided_attempt_id:
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
                accepted_at=item.submitted_at or datetime.now(timezone.utc),
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
                accepted_at=item.submitted_at or datetime.now(timezone.utc),
            )
            stmt = stmt.on_conflict_do_nothing(index_elements=[AccessionRegistry.accession])
            db.execute(stmt)

        if item.status != "submitting":
            sub.attempt_id = None
            sub.lock_acquired_at = None
            sub.lock_expires_at = None
            sub.finalized_attempt_id = attempt_id
            db.add(SubmissionEvent(
                attempt_id=attempt_id,
                entity_type="experiment",
                submission_id=sub.id,
                action=("accepted" if item.status == "accepted" else ("rejected" if item.status == "rejected" else "released")),
                accession=item.accession,
                details=item.response_payload,
            ))

        updated_experiments += 1

    # Process ReadSubmission updates
    for item in payload.reads:
        sub = db.query(ReadSubmission).filter(ReadSubmission.id == item.id).first()
        if not sub:
            raise HTTPException(status_code=404, detail=f"ReadSubmission {item.id} not found")

        if sub.status != "submitting":
            raise HTTPException(status_code=409, detail=f"ReadSubmission {item.id} not in 'submitting' state")
        if sub.attempt_id != provided_attempt_id:
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
                accepted_at=item.submitted_at or datetime.now(timezone.utc),
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
                accepted_at=item.submitted_at or datetime.now(timezone.utc),
            )
            stmt = stmt.on_conflict_do_nothing(index_elements=[AccessionRegistry.accession])
            db.execute(stmt)

        if item.status != "submitting":
            sub.attempt_id = None
            sub.lock_acquired_at = None
            sub.lock_expires_at = None
            sub.finalized_attempt_id = attempt_id
            db.add(SubmissionEvent(
                attempt_id=attempt_id,
                entity_type="read",
                submission_id=sub.id,
                action=("accepted" if item.status == "accepted" else ("rejected" if item.status == "rejected" else "released")),
                accession=item.accession,
                details=item.response_payload,
            ))

        updated_reads += 1

    db.commit()

    return ReportResult(
        updated_counts={
            "samples": updated_samples,
            "experiments": updated_experiments,
            "reads": updated_reads,
        }
    )


# ---------- Dashboard Helpers (attempt-only) ----------
def _counts_for_model(db: Session, model, filters) -> Dict[str, int]:
    q = db.query(model.status, func.count()).filter(*filters).group_by(model.status)
    rows = q.all()
    out: Dict[str, int] = {"draft": 0, "submitting": 0, "accepted": 0, "rejected": 0}
    for status, cnt in rows:
        if status in out:
            out[status] = cnt
        else:
            out[status] = cnt
    return out


def _counts_by_entity_for_attempt(db: Session, attempt_id: UUID) -> Dict[str, Dict[str, int]]:
    """Aggregate counts for an attempt including both active and finalized items.
    Counts rows where attempt_id == attempt_id (active lease) OR
    finalized_attempt_id == attempt_id (finalized outcomes).
    """
    return {
        "samples": _counts_for_model(
            db,
            SampleSubmission,
            [or_(SampleSubmission.attempt_id == attempt_id, SampleSubmission.finalized_attempt_id == attempt_id)],
        ),
        "experiments": _counts_for_model(
            db,
            ExperimentSubmission,
            [or_(ExperimentSubmission.attempt_id == attempt_id, ExperimentSubmission.finalized_attempt_id == attempt_id)],
        ),
        "reads": _counts_for_model(
            db,
            ReadSubmission,
            [or_(ReadSubmission.attempt_id == attempt_id, ReadSubmission.finalized_attempt_id == attempt_id)],
        ),
    }


def _derive_attempt_status(counts_by_entity: Dict[str, Dict[str, int]], lock_expires_at: Optional[datetime]) -> str:
    now = datetime.now()
    submitting = sum(d.get("submitting", 0) for d in counts_by_entity.values())
    accepted = sum(d.get("accepted", 0) for d in counts_by_entity.values())
    if submitting > 0 and (lock_expires_at is None or lock_expires_at > now):
        return "active"
    if submitting == 0 and accepted > 0:
        return "complete"
    if lock_expires_at is not None and lock_expires_at <= now and submitting > 0:
        return "expired"
    total = sum(sum(d.values()) for d in counts_by_entity.values())
    if total == 0:
        return "empty"
    return "idle"


def _get_attempt_items_with_relationships(db: Session, attempt_id: UUID) -> Dict[str, List[ClaimedEntity]]:
    """Return items associated with an attempt (active, finalized, or released via events)
    and include derived parent submission relationships for experiments and reads.
    """
    # Membership by state: active (attempt_id), finalized (finalized_attempt_id), or events (released/claimed/etc.)
    sample_ids: set[UUID] = set(
        x[0]
        for x in db.query(SampleSubmission.id).filter(
            or_(SampleSubmission.attempt_id == attempt_id, SampleSubmission.finalized_attempt_id == attempt_id)
        ).all()
    )
    experiment_ids: set[UUID] = set(
        x[0]
        for x in db.query(ExperimentSubmission.id).filter(
            or_(ExperimentSubmission.attempt_id == attempt_id, ExperimentSubmission.finalized_attempt_id == attempt_id)
        ).all()
    )
    read_ids: set[UUID] = set(
        x[0]
        for x in db.query(ReadSubmission.id).filter(
            or_(ReadSubmission.attempt_id == attempt_id, ReadSubmission.finalized_attempt_id == attempt_id)
        ).all()
    )

    # Include event-only membership (e.g., released-after-claim)
    ev_samples = db.query(SubmissionEvent.submission_id).filter(
        SubmissionEvent.attempt_id == attempt_id,
        SubmissionEvent.entity_type == "sample",
    ).all()
    ev_experiments = db.query(SubmissionEvent.submission_id).filter(
        SubmissionEvent.attempt_id == attempt_id,
        SubmissionEvent.entity_type == "experiment",
    ).all()
    ev_reads = db.query(SubmissionEvent.submission_id).filter(
        SubmissionEvent.attempt_id == attempt_id,
        SubmissionEvent.entity_type == "read",
    ).all()
    sample_ids.update(sid for (sid,) in ev_samples)
    experiment_ids.update(sid for (sid,) in ev_experiments)
    read_ids.update(sid for (sid,) in ev_reads)

    # Load rows
    samples = (
        db.query(SampleSubmission).filter(SampleSubmission.id.in_(sample_ids)).all()
        if sample_ids else []
    )
    experiments = (
        db.query(ExperimentSubmission).filter(ExperimentSubmission.id.in_(experiment_ids)).all()
        if experiment_ids else []
    )
    reads = (
        db.query(ReadSubmission).filter(ReadSubmission.id.in_(read_ids)).all()
        if read_ids else []
    )

    # Build Sample entities (no parent relationships for samples)
    out_samples: List[ClaimedEntity] = [
        ClaimedEntity(
            id=row.id,
            status=row.status,
            prepared_payload=row.prepared_payload,
            accession=row.accession,
        )
        for row in samples
    ]

    # Relationships for Experiments -> Sample / SampleSubmission
    exp_entity_list: List[ClaimedEntity] = []
    if experiments:
        exp_ids = [r.experiment_id for r in experiments]
        exp_sample_pairs = (
            db.query(Experiment.id, Experiment.sample_id)
            .filter(Experiment.id.in_(exp_ids))
            .all()
        )
        sample_id_by_exp: Dict[UUID, UUID] = {eid: sid for (eid, sid) in exp_sample_pairs}

        # Claimed samples in this attempt
        claimed_samples_by_sid: Dict[UUID, SampleSubmission] = {
            r.sample_id: r for r in samples if r.attempt_id == attempt_id and r.status == "submitting"
        }
        missing_sids = [sid for sid in set(sample_id_by_exp.values()) if sid not in claimed_samples_by_sid]
        accepted_samples_by_sid: Dict[UUID, SampleSubmission] = {}
        if missing_sids:
            accepted = (
                db.query(SampleSubmission)
                .filter(SampleSubmission.sample_id.in_(missing_sids), SampleSubmission.status == "accepted")
                .all()
            )
            accepted_samples_by_sid = {r.sample_id: r for r in accepted}

        for row in experiments:
            sid = sample_id_by_exp.get(row.experiment_id)
            parent_ss = claimed_samples_by_sid.get(sid) or accepted_samples_by_sid.get(sid)
            rel = {
                "sample_id": sid,
                "sample_submission_id": (parent_ss.id if parent_ss else None),
                "sample_accession": (parent_ss.accession if parent_ss else getattr(row, "sample_accession", None)),
                "project_accession": getattr(row, "project_accession", None),
            }
            exp_entity_list.append(
                ClaimedEntity(
                    id=row.id,
                    status=row.status,
                    prepared_payload=row.prepared_payload,
                    accession=row.accession,
                    relationships=rel,
                )
            )

    # Relationships for Reads -> Experiment / ExperimentSubmission
    read_entity_list: List[ClaimedEntity] = []
    if reads:
        read_exp_ids = [r.experiment_id for r in reads]
        claimed_exps_by_eid: Dict[UUID, ExperimentSubmission] = {
            r.experiment_id: r for r in experiments if r.attempt_id == attempt_id and r.status == "submitting"
        }
        missing_eids = [eid for eid in set(read_exp_ids) if eid not in claimed_exps_by_eid]
        accepted_exps_by_eid: Dict[UUID, ExperimentSubmission] = {}
        if missing_eids:
            accepted = (
                db.query(ExperimentSubmission)
                .filter(ExperimentSubmission.experiment_id.in_(missing_eids), ExperimentSubmission.status == "accepted")
                .all()
            )
            accepted_exps_by_eid = {r.experiment_id: r for r in accepted}

        for row in reads:
            exp_parent = claimed_exps_by_eid.get(row.experiment_id) or accepted_exps_by_eid.get(row.experiment_id)
            rel = {
                "experiment_id": row.experiment_id,
                "experiment_submission_id": (exp_parent.id if exp_parent else None),
                "experiment_accession": (exp_parent.accession if exp_parent else getattr(row, "experiment_accession", None)),
            }
            read_entity_list.append(
                ClaimedEntity(
                    id=row.id,
                    status=row.status,
                    prepared_payload=row.prepared_payload,
                    accession=row.accession,
                    relationships=rel,
                )
            )

    return {"samples": out_samples, "experiments": exp_entity_list, "reads": read_entity_list}

@router.get("/attempts")
def list_attempts(
    *,
    db: Session = Depends(get_db),
    active_only: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
) -> Dict[str, Any]:
    q = db.query(SubmissionAttempt)
    total = q.count()
    items = (
        q.order_by(SubmissionAttempt.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    now = datetime.now()
    results: List[Dict[str, Any]] = []
    for a in items:
        counts = _counts_by_entity_for_attempt(db, a.id)
        status = _derive_attempt_status(counts, a.lock_expires_at)
        if active_only and status != "active":
            continue
        results.append(
            {
                "attempt_id": str(a.id),
                "organism_key": a.organism_key,
                "campaign_label": a.campaign_label,
                "status": status,
                "lock_expires_at": a.lock_expires_at,
                "created_at": a.created_at,
                "updated_at": a.updated_at,
                "counts_by_entity": counts,
            }
        )
    return {"items": results, "page": page, "page_size": page_size, "total": total}


@router.get("/attempts/{attempt_id}")
def get_attempt(
    *,
    attempt_id: UUID,
    db: Session = Depends(get_db),
    include_items: bool = Query(False),
) -> Dict[str, Any]:
    a = db.query(SubmissionAttempt).filter(SubmissionAttempt.id == attempt_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Attempt not found")
    counts = _counts_by_entity_for_attempt(db, attempt_id)
    status = _derive_attempt_status(counts, a.lock_expires_at)
    result: Dict[str, Any] = {
        "attempt_id": str(a.id),
        "organism_key": a.organism_key,
        "campaign_label": a.campaign_label,
        "status": status,
        "lock_expires_at": a.lock_expires_at,
        "created_at": a.created_at,
        "updated_at": a.updated_at,
        "counts_by_entity": counts,
    }
    if include_items:
        items = _get_attempt_items_with_relationships(db, attempt_id)
        # serialize pydantic models
        result["items"] = {
            k: [e.dict() for e in v] for k, v in items.items()
        }
    return result


@router.get("/attempts/{attempt_id}/items")
def get_attempt_items(
    *,
    attempt_id: UUID,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    items = _get_attempt_items_with_relationships(db, attempt_id)
    return {k: [e.dict() for e in v] for k, v in items.items()}


@router.get("/organisms/{organism_key}/summary")
def organism_summary(
    *,
    organism_key: str,
    db: Session = Depends(get_db),
    recent_attempts: int = Query(5, ge=1, le=50),
) -> Dict[str, Any]:
    # latest attempts for this organism
    attempts = (
        db.query(SubmissionAttempt)
        .filter(SubmissionAttempt.organism_key == organism_key)
        .order_by(SubmissionAttempt.created_at.desc())
        .limit(recent_attempts)
        .all()
    )
    latest = []
    for a in attempts:
        a_counts = _counts_by_entity_for_attempt(db, a.id)
        latest.append({
            "attempt_id": str(a.id),
            "status": _derive_attempt_status(a_counts, a.lock_expires_at),
            "lock_expires_at": a.lock_expires_at,
            "created_at": a.created_at,
        })
    # counts across organism (properly scoped via joins)
    # Samples: join to Sample for organism_key
    s_rows = (
        db.query(SampleSubmission.status, func.count())
        .join(Sample, SampleSubmission.sample_id == Sample.id)
        .filter(Sample.organism_key == organism_key)
        .group_by(SampleSubmission.status)
        .all()
    )
    s_counts: Dict[str, int] = {"draft": 0, "submitting": 0, "accepted": 0, "rejected": 0}
    for st, cnt in s_rows:
        s_counts[st] = cnt

    # Experiments: ExperimentSubmission -> Experiment -> Sample
    e_rows = (
        db.query(ExperimentSubmission.status, func.count())
        .join(Experiment, ExperimentSubmission.experiment_id == Experiment.id)
        .join(Sample, Experiment.sample_id == Sample.id)
        .filter(Sample.organism_key == organism_key)
        .group_by(ExperimentSubmission.status)
        .all()
    )
    e_counts: Dict[str, int] = {"draft": 0, "submitting": 0, "accepted": 0, "rejected": 0}
    for st, cnt in e_rows:
        e_counts[st] = cnt

    # Reads: ReadSubmission -> Read -> Experiment -> Sample
    r_rows = (
        db.query(ReadSubmission.status, func.count())
        .join(Read, ReadSubmission.read_id == Read.id)
        .join(Experiment, Read.experiment_id == Experiment.id)
        .join(Sample, Experiment.sample_id == Sample.id)
        .filter(Sample.organism_key == organism_key)
        .group_by(ReadSubmission.status)
        .all()
    )
    r_counts: Dict[str, int] = {"draft": 0, "submitting": 0, "accepted": 0, "rejected": 0}
    for st, cnt in r_rows:
        r_counts[st] = cnt

    counts_by_entity = {
        "samples": s_counts,
        "experiments": e_counts,
        "reads": r_counts,
    }
    # Active attempts for this organism
    attempts = db.query(SubmissionAttempt).filter(SubmissionAttempt.organism_key == organism_key).all()
    active = []
    now = datetime.now()
    for a in attempts:
        a_counts = _counts_by_entity_for_attempt(db, a.id)
        if _derive_attempt_status(a_counts, a.lock_expires_at) == "active":
            active.append({"attempt_id": str(a.id), "lock_expires_at": a.lock_expires_at})
    return {
        "organism_key": organism_key,
        "latest_attempts": latest,
        "active_attempts": active,
        "counts_by_entity": counts_by_entity,
    }

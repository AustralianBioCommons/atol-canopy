from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.broker import SubmissionAttempt
from app.models.experiment import ExperimentSubmission
from app.models.project import ProjectSubmission
from app.models.read import ReadSubmission
from app.models.sample import SampleSubmission


def expire_leases(db: Session) -> Dict[str, int]:
    now = datetime.now(timezone.utc)

    def _expire_submissions(model) -> int:
        stmt = (
            update(model)
            .where(model.status == "submitting")
            .where(model.lock_expires_at.isnot(None))
            .where(model.lock_expires_at < now)
            .values(
                status="draft",
                attempt_id=None,
                lock_acquired_at=None,
                lock_expires_at=None,
            )
        )
        result = db.execute(stmt)
        return result.rowcount or 0

    def _expire_attempts() -> int:
        stmt = (
            update(SubmissionAttempt)
            .where(SubmissionAttempt.status == "processing")
            .where(SubmissionAttempt.lock_expires_at.isnot(None))
            .where(SubmissionAttempt.lock_expires_at < now)
            .values(status="expired")
        )
        result = db.execute(stmt)
        return result.rowcount or 0

    return {
        "project_submissions": _expire_submissions(ProjectSubmission),
        "sample_submissions": _expire_submissions(SampleSubmission),
        "experiment_submissions": _expire_submissions(ExperimentSubmission),
        "read_submissions": _expire_submissions(ReadSubmission),
        "attempts": _expire_attempts(),
    }

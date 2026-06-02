from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.experiment import Experiment
from app.models.qc_read import QcRead, QcReadSubmission
from app.models.read import Read


class QcReadSubmissionService:
    """Query helpers for QcReadSubmission records."""

    def get_by_qc_read_id(self, db: Session, qc_read_id: UUID) -> List[QcReadSubmission]:
        return db.query(QcReadSubmission).filter(QcReadSubmission.qc_read_id == qc_read_id).all()

    def get_by_experiment_id(self, db: Session, experiment_id: UUID) -> List[QcReadSubmission]:
        return (
            db.query(QcReadSubmission)
            .join(QcRead, QcRead.id == QcReadSubmission.qc_read_id)
            .join(Read, Read.id == QcRead.read_id)
            .filter(Read.experiment_id == experiment_id)
            .all()
        )

    def get_by_project_id(self, db: Session, project_id: UUID) -> List[QcReadSubmission]:
        return (
            db.query(QcReadSubmission)
            .join(QcRead, QcRead.id == QcReadSubmission.qc_read_id)
            .join(Read, Read.id == QcRead.read_id)
            .join(Experiment, Experiment.id == Read.experiment_id)
            .filter(Experiment.project_id == project_id)
            .all()
        )

    def get_by_accession(self, db: Session, accession: str) -> Optional[QcReadSubmission]:
        return db.query(QcReadSubmission).filter(QcReadSubmission.accession == accession).first()


qc_read_submission_service = QcReadSubmissionService()

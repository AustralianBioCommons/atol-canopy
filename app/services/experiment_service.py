from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.experiment import Experiment, ExperimentSubmission
from app.schemas.experiment import ExperimentCreate, ExperimentUpdate
from app.services.base_service import BaseService


class ExperimentService(BaseService[Experiment, ExperimentCreate, ExperimentUpdate]):
    """Service for Experiment operations."""
    
    def get_by_sample_id(self, db: Session, sample_id: UUID) -> List[Experiment]:
        """Get experiments by sample ID."""
        return db.query(Experiment).filter(Experiment.sample_id == sample_id).all()
    
    def get_by_bpa_package_id(self, db: Session, bpa_package_id: str) -> Optional[Experiment]:
        """Get experiment by BPA package ID."""
        return db.query(Experiment).filter(Experiment.bpa_package_id == bpa_package_id).first()
    
    def get_multi_with_filters(
        self, 
        db: Session, 
        *, 
        skip: int = 0, 
        limit: int = 100,
        sample_id: Optional[UUID] = None,
        bpa_package_id: Optional[str] = None
    ) -> List[Experiment]:
        """Get experiments with filters."""
        query = db.query(Experiment)
        if sample_id:
            query = query.filter(Experiment.sample_id == sample_id)
        if bpa_package_id:
            query = query.filter(Experiment.bpa_package_id.ilike(f"%{bpa_package_id}%"))
        return query.offset(skip).limit(limit).all()


class ExperimentSubmissionService(BaseService[ExperimentSubmission, ExperimentCreate, ExperimentUpdate]):
    """Service for ExperimentSubmission operations."""
    
    def get_by_experiment_id(self, db: Session, experiment_id: UUID) -> List[ExperimentSubmission]:
        """Get submission experiments by experiment ID."""
        return db.query(ExperimentSubmission).filter(ExperimentSubmission.experiment_id == experiment_id).all()
    
    def get_by_sample_id(self, db: Session, sample_id: UUID) -> List[ExperimentSubmission]:
        """Get submission experiments by sample ID."""
        return db.query(ExperimentSubmission).filter(ExperimentSubmission.sample_id == sample_id).all()
    
    def get_by_project_id(self, db: Session, project_id: UUID) -> List[ExperimentSubmission]:
        """Get submission experiments by project ID."""
        return db.query(ExperimentSubmission).filter(ExperimentSubmission.project_id == project_id).all()
    
    def get_by_accession(self, db: Session, accession: str) -> Optional[ExperimentSubmission]:
        """Get submission experiment by accession."""
        return db.query(ExperimentSubmission).filter(ExperimentSubmission.accession == accession).first()


# ExperimentFetched model has been removed from the schema


experiment_service = ExperimentService(Experiment)
experiment_submission_service = ExperimentSubmissionService(ExperimentSubmission)

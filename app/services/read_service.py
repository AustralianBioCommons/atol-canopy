from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.read import Read, ReadSubmission
from app.schemas.read import ReadCreate, ReadUpdate
from app.services.base_service import BaseService


class ReadService(BaseService[Read, ReadCreate, ReadUpdate]):
    """Service for Read operations."""
    
    def get_by_experiment_id(self, db: Session, experiment_id: UUID) -> List[Read]:
        """Get reads by experiment ID."""
        return db.query(Read).filter(Read.experiment_id == experiment_id).all()
    
    def get_by_bpa_resource_id(self, db: Session, bpa_resource_id: str) -> Optional[Read]:
        """Get read by BPA resource ID."""
        return db.query(Read).filter(Read.bpa_resource_id == bpa_resource_id).first()
    
    def get_multi_with_filters(
        self, 
        db: Session, 
        *, 
        skip: int = 0, 
        limit: int = 100,
        experiment_id: Optional[UUID] = None,
        bpa_resource_id: Optional[str] = None
    ) -> List[Read]:
        """Get reads with filters."""
        query = db.query(Read)
        if experiment_id:
            query = query.filter(Read.experiment_id == experiment_id)
        if bpa_resource_id:
            query = query.filter(Read.bpa_resource_id.ilike(f"%{bpa_resource_id}%"))
        return query.offset(skip).limit(limit).all()


class ReadSubmissionService(BaseService[ReadSubmission, ReadCreate, ReadUpdate]):
    """Service for ReadSubmission operations."""
    
    def get_by_read_id(self, db: Session, read_id: UUID) -> List[ReadSubmission]:
        """Get submission reads by read ID."""
        return db.query(ReadSubmission).filter(ReadSubmission.read_id == read_id).all()
    
    def get_by_experiment_id(self, db: Session, experiment_id: UUID) -> List[ReadSubmission]:
        """Get submission reads by experiment ID."""
        return db.query(ReadSubmission).filter(ReadSubmission.experiment_id == experiment_id).all()
    
    def get_by_project_id(self, db: Session, project_id: UUID) -> List[ReadSubmission]:
        """Get submission reads by project ID."""
        return db.query(ReadSubmission).filter(ReadSubmission.project_id == project_id).all()
    
    def get_by_accession(self, db: Session, accession: str) -> Optional[ReadSubmission]:
        """Get submission read by accession."""
        return db.query(ReadSubmission).filter(ReadSubmission.accession == accession).first()


read_service = ReadService(Read)
read_submission_service = ReadSubmissionService(ReadSubmission)

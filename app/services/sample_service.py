from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.sample import Sample, SampleSubmission
from app.schemas.sample import SampleCreate, SampleUpdate
from app.services.base_service import BaseService


class SampleService(BaseService[Sample, SampleCreate, SampleUpdate]):
    """Service for Sample operations."""

    def get_by_organism_key(self, db: Session, organism_key: str) -> List[Sample]:
        """Get samples by organism key."""
        return db.query(Sample).filter(Sample.organism_key == organism_key).all()

    def get_by_bpa_sample_id(self, db: Session, bpa_sample_id: str) -> Optional[Sample]:
        """Get sample by BPA sample ID."""
        return db.query(Sample).filter(Sample.bpa_sample_id == bpa_sample_id).first()

    def get_multi_with_filters(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        organism_key: Optional[str] = None,
        bpa_sample_id: Optional[str] = None,
    ) -> List[Sample]:
        """Get samples with filters."""
        query = db.query(Sample)
        if organism_key:
            query = query.filter(Sample.organism_key == organism_key)
        if bpa_sample_id:
            query = query.filter(Sample.bpa_sample_id.ilike(f"%{bpa_sample_id}%"))
        return query.offset(skip).limit(limit).all()


class SampleSubmissionService(BaseService[SampleSubmission, SampleCreate, SampleUpdate]):
    """Service for SampleSubmission operations."""

    def get_by_sample_id(self, db: Session, sample_id: UUID) -> List[SampleSubmission]:
        """Get submission samples by sample ID."""
        return db.query(SampleSubmission).filter(SampleSubmission.sample_id == sample_id).all()

    def get_by_accession(self, db: Session, accession: str) -> Optional[SampleSubmission]:
        """Get submission sample by accession."""
        return db.query(SampleSubmission).filter(SampleSubmission.accession == accession).first()

    def get_by_biosample_accession(
        self, db: Session, biosample_accession: str
    ) -> Optional[SampleSubmission]:
        """Get submission sample by biosample accession."""
        return (
            db.query(SampleSubmission)
            .filter(SampleSubmission.biosample_accession == biosample_accession)
            .first()
        )


# SampleFetched model has been removed from the schema


sample_service = SampleService(Sample)
sample_submission_service = SampleSubmissionService(SampleSubmission)

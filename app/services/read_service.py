from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.read import Read
from app.schemas.read import ReadCreate, ReadUpdate
from app.services.base_service import BaseService


class ReadService(BaseService[Read, ReadCreate, ReadUpdate]):
    """Service for Read operations."""

    def get_by_experiment_id(self, db: Session, experiment_id: UUID) -> List[Read]:
        return db.query(Read).filter(Read.experiment_id == experiment_id).all()

    def get_by_bpa_resource_id(self, db: Session, bpa_resource_id: str) -> Optional[Read]:
        return db.query(Read).filter(Read.bpa_resource_id == bpa_resource_id).first()

    def get_multi_with_filters(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        experiment_id: Optional[UUID] = None,
        bpa_resource_id: Optional[str] = None,
    ) -> List[Read]:
        query = db.query(Read)
        if experiment_id:
            query = query.filter(Read.experiment_id == experiment_id)
        if bpa_resource_id:
            query = query.filter(Read.bpa_resource_id.ilike(f"%{bpa_resource_id}%"))
        return query.offset(skip).limit(limit).all()


read_service = ReadService(Read)

from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.bpa_initiative import BPAInitiative
from app.schemas.bpa_initiative import BPAInitiativeCreate, BPAInitiativeUpdate
from app.services.base_service import BaseService


class BPAInitiativeService(BaseService[BPAInitiative, BPAInitiativeCreate, BPAInitiativeUpdate]):
    """Service for BPAInitiative operations."""
    
    def get_by_title(self, db: Session, title: str) -> Optional[BPAInitiative]:
        """Get BPA initiative by title."""
        return db.query(BPAInitiative).filter(BPAInitiative.title == title).first()
    
    def get_by_project_code(self, db: Session, project_code: str) -> Optional[BPAInitiative]:
        """Get BPA initiative by project code."""
        return db.query(BPAInitiative).filter(BPAInitiative.project_code == project_code).first()
    
    def get_multi_with_filters(
        self, 
        db: Session, 
        *, 
        skip: int = 0, 
        limit: int = 100,
        title: Optional[str] = None,
        project_code: Optional[str] = None,
        url: Optional[str] = None
    ) -> List[BPAInitiative]:
        """Get BPA initiatives with filters."""
        query = db.query(BPAInitiative)
        if title:
            query = query.filter(BPAInitiative.title.ilike(f"%{title}%"))
        if project_code:
            query = query.filter(BPAInitiative.project_code == project_code)
        if url:
            query = query.filter(BPAInitiative.url.ilike(f"%{url}%"))
        return query.offset(skip).limit(limit).all()


bpa_initiative_service = BPAInitiativeService(BPAInitiative)

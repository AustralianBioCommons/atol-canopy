from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services.base_service import BaseService


class ProjectService(BaseService[Project, ProjectCreate, ProjectUpdate]):
    """Service for Project operations."""

    def get_by_accession(self, db: Session, accession: str) -> Optional[Project]:
        """Get project by accession."""
        return db.query(Project).filter(Project.accession == accession).first()

    def get_by_title(self, db: Session, title: str) -> List[Project]:
        """Get projects by title."""
        return db.query(Project).filter(Project.title.ilike(f"%{title}%")).all()

    def get_by_description(self, db: Session, description: str) -> List[Project]:
        """Get projects by description."""
        return db.query(Project).filter(Project.description.ilike(f"%{description}%")).all()

    def get_multi_with_filters(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        title: Optional[str] = None,
        accession: Optional[str] = None,
        description: Optional[str] = None,
    ) -> List[Project]:
        """Get projects with filters."""
        query = db.query(Project)
        if title:
            query = query.filter(Project.title.ilike(f"%{title}%"))
        if accession:
            query = query.filter(Project.accession == accession)
        if description:
            query = query.filter(Project.description.ilike(f"%{description}%"))
        return query.offset(skip).limit(limit).all()


project_service = ProjectService(Project)

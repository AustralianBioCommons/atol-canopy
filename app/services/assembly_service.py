from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.assembly import Assembly, AssemblyFile, AssemblyRead, AssemblySubmission
from app.schemas.assembly import (
    AssemblyCreate,
    AssemblyFileCreate,
    AssemblyFileUpdate,
    AssemblySubmissionCreate,
    AssemblySubmissionUpdate,
    AssemblyUpdate,
)
from app.services.base_service import BaseService


class AssemblyService(BaseService[Assembly, AssemblyCreate, AssemblyUpdate]):
    """Service for Assembly operations."""

    def get_by_project_id(self, db: Session, project_id: UUID) -> List[Assembly]:
        """Get assemblies by project ID."""
        return db.query(Assembly).filter(Assembly.project_id == project_id).all()

    def get_by_organism_key(self, db: Session, organism_key: str) -> List[Assembly]:
        """Get assemblies by organism key."""
        return db.query(Assembly).filter(Assembly.organism_key == organism_key).all()

    def get_multi_with_filters(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        project_id: Optional[UUID] = None,
        organism_key: Optional[str] = None,
        assembly_name: Optional[str] = None,
        assembly_type: Optional[str] = None,
    ) -> List[Assembly]:
        """Get assemblies with filters."""
        query = db.query(Assembly)
        if project_id:
            query = query.filter(Assembly.project_id == project_id)
        if organism_key:
            query = query.filter(Assembly.organism_key == organism_key)
        if assembly_name:
            query = query.filter(Assembly.assembly_name == assembly_name)
        if assembly_type:
            query = query.filter(Assembly.assembly_type == assembly_type)
        return query.offset(skip).limit(limit).all()


class AssemblySubmissionService(
    BaseService[AssemblySubmission, AssemblySubmissionCreate, AssemblySubmissionUpdate]
):
    """Service for AssemblySubmission operations."""

    def get_by_assembly_id(self, db: Session, assembly_id: UUID) -> List[AssemblySubmission]:
        """Get submission assemblies by assembly ID."""
        return (
            db.query(AssemblySubmission).filter(AssemblySubmission.assembly_id == assembly_id).all()
        )

    def get_by_accession(self, db: Session, accession: str) -> Optional[AssemblySubmission]:
        """Get submission assembly by accession."""
        return (
            db.query(AssemblySubmission).filter(AssemblySubmission.accession == accession).first()
        )

    def get_accepted_by_assembly_id(
        self, db: Session, assembly_id: UUID
    ) -> Optional[AssemblySubmission]:
        """Get accepted submission for an assembly."""
        return (
            db.query(AssemblySubmission)
            .filter(
                AssemblySubmission.assembly_id == assembly_id,
                AssemblySubmission.status == "accepted",
            )
            .first()
        )


class AssemblyFileService(BaseService[AssemblyFile, AssemblyFileCreate, AssemblyFileUpdate]):
    """Service for AssemblyFile operations."""

    def get_by_assembly_id(self, db: Session, assembly_id: UUID) -> List[AssemblyFile]:
        """Get files by assembly ID."""
        return db.query(AssemblyFile).filter(AssemblyFile.assembly_id == assembly_id).all()

    def get_by_assembly_and_type(
        self, db: Session, assembly_id: UUID, file_type: str
    ) -> List[AssemblyFile]:
        """Get files by assembly ID and file type."""
        return (
            db.query(AssemblyFile)
            .filter(AssemblyFile.assembly_id == assembly_id, AssemblyFile.file_type == file_type)
            .all()
        )


class AssemblyReadService(BaseService[AssemblyRead, AssemblyCreate, AssemblyUpdate]):
    """Service for AssemblyRead operations."""

    def get_by_assembly_id(self, db: Session, assembly_id: UUID) -> List[AssemblyRead]:
        """Get assembly reads by assembly ID."""
        return db.query(AssemblyRead).filter(AssemblyRead.assembly_id == assembly_id).all()


assembly_service = AssemblyService(Assembly)
assembly_submission_service = AssemblySubmissionService(AssemblySubmission)
assembly_file_service = AssemblyFileService(AssemblyFile)
assembly_read_service = AssemblyReadService(AssemblyRead)

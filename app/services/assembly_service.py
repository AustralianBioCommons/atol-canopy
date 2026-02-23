from typing import List, Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.assembly import Assembly, AssemblyFile, AssemblyRead, AssemblySubmission
from app.models.experiment import Experiment
from app.models.organism import Organism
from app.models.sample import Sample
from app.schemas.assembly import (
    AssemblyCreate,
    AssemblyFileCreate,
    AssemblyFileUpdate,
    AssemblySubmissionCreate,
    AssemblySubmissionUpdate,
    AssemblyUpdate,
)
from app.services.assembly_helper import determine_assembly_data_types, get_detected_platforms
from app.services.base_service import BaseService


class AssemblyService(BaseService[Assembly, AssemblyCreate, AssemblyUpdate]):
    """Service for Assembly operations."""

    def create(self, db: Session, *, obj_in: AssemblyCreate) -> Assembly:
        """Create assembly with auto-incremented version.

        Version is automatically incremented based on existing assemblies
        for the same (data_types, organism_key, sample_id) combination.
        """
        # Find the highest version number for this combination
        max_version = (
            db.query(func.max(Assembly.version))
            .filter(
                Assembly.data_types == obj_in.data_types,
                Assembly.organism_key == obj_in.organism_key,
                Assembly.sample_id == obj_in.sample_id,
            )
            .scalar()
        )

        # Auto-increment version (start at 1 if no previous versions)
        next_version = (max_version or 0) + 1

        # Create assembly with auto-incremented version
        obj_in_data = obj_in.model_dump()
        obj_in_data["version"] = next_version

        db_obj = Assembly(**obj_in_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

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

    def create_from_experiments(
        self,
        db: Session,
        *,
        tax_id: int,
        assembly_in,  # AssemblyCreateFromExperiments
    ) -> tuple[Assembly, dict]:
        """Create assembly based on experiments for a given tax_id.

        Automatically determines data_types by analyzing all experiments
        related to the organism (via tax_id).

        Args:
            db: Database session
            tax_id: Taxonomy ID of the organism
            assembly_in: Assembly creation data (organism_key and data_types auto-determined)

        Returns:
            Tuple of (created Assembly, platform detection info)

        Raises:
            ValueError: If organism not found, no experiments found, or no valid platforms detected
        """
        # 1. Get organism by tax_id
        organism = db.query(Organism).filter(Organism.tax_id == tax_id).first()
        if not organism:
            raise ValueError(f"Organism with tax_id {tax_id} not found")

        # 2. Get all samples for this organism
        samples = db.query(Sample).filter(Sample.organism_key == organism.grouping_key).all()
        if not samples:
            raise ValueError(f"No samples found for organism {organism.grouping_key} (tax_id: {tax_id})")

        # 3. Get all experiments for these samples
        sample_ids = [sample.id for sample in samples]
        experiments = db.query(Experiment).filter(Experiment.sample_id.in_(sample_ids)).all()

        if not experiments:
            raise ValueError(
                f"No experiments found for organism {organism.grouping_key} (tax_id: {tax_id})"
            )

        # 4. Determine data_types from experiments (unless explicitly provided)
        platform_info = get_detected_platforms(experiments)
        obj_in_data = assembly_in.model_dump()

        if obj_in_data.get("data_types") is None:
            data_types = determine_assembly_data_types(experiments)
            obj_in_data["data_types"] = data_types

        # 5. Add organism_key from tax_id lookup
        obj_in_data["organism_key"] = organism.grouping_key

        # 6. Create assembly using standard create method (handles versioning)
        assembly_create = AssemblyCreate(**obj_in_data)
        assembly = self.create(db, obj_in=assembly_create)

        return assembly, platform_info


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

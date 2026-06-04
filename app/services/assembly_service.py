from typing import List, Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.assembly import (
    Assembly,
    AssemblyFile,
    AssemblyRead,
    AssemblyRun,
    AssemblyStageRun,
    AssemblyStageRunFile,
    AssemblySubmission,
)
from app.models.experiment import Experiment
from app.models.organism import Organism
from app.models.sample import Sample
from app.schemas.assembly import (
    AssemblyCreate,
    AssemblyFileCreate,
    AssemblyFileUpdate,
    AssemblyRunCreate,
    AssemblyStageRunCreate,
    AssemblyStageRunUpdate,
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
        for the same (data_types, taxon_id, sample_id) combination.
        """
        # Find the highest version number for this combination
        max_version = (
            db.query(func.max(Assembly.version))
            .filter(
                Assembly.data_types == obj_in.data_types,
                Assembly.taxon_id == obj_in.taxon_id,
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

    def get_by_taxon_id(self, db: Session, taxon_id: int) -> List[Assembly]:
        """Get assemblies by organism taxon ID."""
        return db.query(Assembly).filter(Assembly.taxon_id == taxon_id).all()

    def get_multi_with_filters(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        project_id: Optional[UUID] = None,
        taxon_id: Optional[int] = None,
        assembly_name: Optional[str] = None,
        assembly_type: Optional[str] = None,
    ) -> List[Assembly]:
        """Get assemblies with filters."""
        query = db.query(Assembly)
        if project_id:
            query = query.filter(Assembly.project_id == project_id)
        if taxon_id is not None:
            query = query.filter(Assembly.taxon_id == taxon_id)
        if assembly_name:
            query = query.filter(Assembly.assembly_name == assembly_name)
        if assembly_type:
            query = query.filter(Assembly.assembly_type == assembly_type)
        return query.offset(skip).limit(limit).all()

    def create_from_experiments(
        self,
        db: Session,
        *,
        taxon_id: int,
        assembly_in,  # AssemblyCreateFromExperiments
    ) -> tuple[Assembly, dict]:
        """Create assembly based on experiments for a given taxon_id.

        Automatically determines data_types by analyzing all experiments
        related to the organism (via taxon_id).

        Args:
            db: Database session
            taxon_id: Taxonomy ID of the organism
            assembly_in: Assembly creation data (data_types auto-determined)

        Returns:
            Tuple of (created Assembly, platform detection info)

        Raises:
            ValueError: If organism not found, no experiments found, or no valid platforms detected
        """
        # 1. Get organism by taxon_id
        organism = db.query(Organism).filter(Organism.taxon_id == taxon_id).first()
        if not organism:
            raise ValueError(f"Organism with taxon_id {taxon_id} not found")

        # 2. Get all samples for this organism
        samples = db.query(Sample).filter(Sample.taxon_id == organism.taxon_id).all()
        if not samples:
            raise ValueError(f"No samples found for organism taxon_id {organism.taxon_id}")

        # 3. Get all experiments for these samples
        sample_ids = [sample.id for sample in samples]
        experiments = db.query(Experiment).filter(Experiment.sample_id.in_(sample_ids)).all()

        if not experiments:
            raise ValueError(f"No experiments found for organism taxon_id {organism.taxon_id}")

        # 4. Determine data_types from experiments (unless explicitly provided)
        platform_info = get_detected_platforms(experiments)
        obj_in_data = assembly_in.model_dump()

        if obj_in_data.get("data_types") is None:
            data_types = determine_assembly_data_types(experiments)
            obj_in_data["data_types"] = data_types

        # 5. Add taxon_id from lookup
        obj_in_data["taxon_id"] = organism.taxon_id

        # 6. Create assembly using standard create method (handles versioning)
        assembly_create = AssemblyCreate(**obj_in_data)
        assembly = self.create(db, obj_in=assembly_create)

        return assembly, platform_info

    def get_next_version(
        self,
        db: Session,
        *,
        taxon_id: int,
        sample_id: UUID,
        data_types: str,
    ) -> int:
        max_assembly = (
            db.query(func.max(Assembly.version))
            .filter(
                Assembly.data_types == data_types,
                Assembly.taxon_id == taxon_id,
                Assembly.sample_id == sample_id,
            )
            .scalar()
        )
        return (max_assembly or 0) + 1

    def get_next_version_for_intent(
        self,
        db: Session,
        *,
        taxon_id: int,
        long_read_specimen_sample_id: UUID,
    ) -> int:
        """Return the next version scoped by (taxon_id, long_read_specimen_sample_id).

        This is the versioning strategy for the intent flow. Versions are shared
        across all assemblies for the same taxon + long-read specimen, regardless
        of data_types or hic_specimen_sample_id.
        """
        max_version = (
            db.query(func.max(Assembly.version))
            .filter(
                Assembly.taxon_id == taxon_id,
                Assembly.long_read_specimen_sample_id == long_read_specimen_sample_id,
            )
            .scalar()
        )
        return (max_version or 0) + 1

    def create_from_intent(
        self,
        db: Session,
        *,
        taxon_id: int,
        long_read_specimen_sample_id: UUID,
        hic_specimen_sample_ids: Optional[List[UUID]],
        data_types: str,
        tol_id: Optional[str],
        project_id: Optional[UUID],
        manifest_json: Optional[dict] = None,
    ) -> Assembly:
        """Create an Assembly at manifest-request time.

        Versioning is scoped by (taxon_id, long_read_specimen_sample_id) only —
        data_types and hic_specimen_sample_ids are excluded from the version key.
        sample_id is set to long_read_specimen_sample_id for backward compatibility.
        """
        version = self.get_next_version_for_intent(
            db,
            taxon_id=taxon_id,
            long_read_specimen_sample_id=long_read_specimen_sample_id,
        )
        # Keep singular FK column pointing to the first HiC sample for backwards compatibility
        hic_specimen_sample_id = hic_specimen_sample_ids[0] if hic_specimen_sample_ids else None
        assembly = Assembly(
            taxon_id=taxon_id,
            sample_id=long_read_specimen_sample_id,
            long_read_specimen_sample_id=long_read_specimen_sample_id,
            hic_specimen_sample_id=hic_specimen_sample_id,
            hic_specimen_sample_ids=[str(sid) for sid in hic_specimen_sample_ids]
            if hic_specimen_sample_ids
            else None,
            data_types=data_types,
            version=version,
            tol_id=tol_id,
            project_id=project_id,
            manifest_json=manifest_json,
        )
        db.add(assembly)
        db.commit()
        db.refresh(assembly)
        return assembly


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


class AssemblyRunService(BaseService[AssemblyRun, AssemblyRunCreate, AssemblyRunCreate]):
    """Service for AssemblyRun (pipeline invocation) operations."""

    def get_by_assembly_id(self, db: Session, *, assembly_id: UUID) -> List[AssemblyRun]:
        return (
            db.query(AssemblyRun)
            .filter(AssemblyRun.assembly_id == assembly_id)
            .order_by(AssemblyRun.created_at.desc())
            .all()
        )

    def create_for_assembly(
        self,
        db: Session,
        *,
        assembly_id: UUID,
        run_in: AssemblyRunCreate,
    ) -> AssemblyRun:
        existing_run = (
            db.query(AssemblyRun)
            .filter(
                AssemblyRun.assembly_id == assembly_id,
                AssemblyRun.github_repo == run_in.github_repo,
                AssemblyRun.git_commit == run_in.git_commit,
            )
            .first()
        )
        if existing_run:
            raise ValueError(
                "Assembly run already exists for this assembly_id, github_repo, and git_commit."
            )

        run = AssemblyRun(
            assembly_id=assembly_id,
            github_repo=run_in.github_repo,
            git_commit=run_in.git_commit,
        )
        db.add(run)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise ValueError(
                "Assembly run already exists for this assembly_id, github_repo, and git_commit"
            ) from None
        db.refresh(run)
        return run


class AssemblyStageRunService(
    BaseService[AssemblyStageRun, AssemblyStageRunCreate, AssemblyStageRunUpdate]
):
    """Service for AssemblyStageRun operations."""

    def get_by_assembly_run_id(
        self, db: Session, *, assembly_run_id: UUID
    ) -> List[AssemblyStageRun]:
        return (
            db.query(AssemblyStageRun)
            .filter(AssemblyStageRun.assembly_run_id == assembly_run_id)
            .order_by(AssemblyStageRun.created_at.desc())
            .all()
        )

    def create_with_files(
        self,
        db: Session,
        *,
        assembly_run_id: UUID,
        run_in: AssemblyStageRunCreate,
    ) -> AssemblyStageRun:
        run = AssemblyStageRun(
            assembly_run_id=assembly_run_id,
            stage_name=run_in.stage_name,
            external_run_id=run_in.external_run_id,
            data=run_in.data,
            started_at=run_in.started_at,
            completed_at=run_in.completed_at,
        )
        db.add(run)
        db.flush()
        for f in run_in.files:
            db.add(
                AssemblyStageRunFile(
                    assembly_stage_run_id=run.id,
                    storage_type=f.storage_type,
                    endpoint=f.endpoint,
                    location_root=f.location_root,
                    location_path=f.location_path,
                    sha256sum=f.sha256sum,
                )
            )
        db.commit()
        db.refresh(run)
        return run

    def update_with_files(
        self,
        db: Session,
        *,
        db_obj: AssemblyStageRun,
        update_in: AssemblyStageRunUpdate,
    ) -> AssemblyStageRun:
        if update_in.external_run_id is not None:
            db_obj.external_run_id = update_in.external_run_id
        if update_in.data is not None:
            db_obj.data = update_in.data
        if update_in.started_at is not None:
            db_obj.started_at = update_in.started_at
        if update_in.completed_at is not None:
            db_obj.completed_at = update_in.completed_at

        if update_in.files is not None:
            # Replace all files
            db.query(AssemblyStageRunFile).filter(
                AssemblyStageRunFile.assembly_stage_run_id == db_obj.id
            ).delete()
            for f in update_in.files:
                db.add(
                    AssemblyStageRunFile(
                        assembly_stage_run_id=db_obj.id,
                        storage_type=f.storage_type,
                        endpoint=f.endpoint,
                        location_root=f.location_root,
                        location_path=f.location_path,
                        sha256sum=f.sha256sum,
                    )
                )

        db.commit()
        db.refresh(db_obj)
        return db_obj


assembly_service = AssemblyService(Assembly)
assembly_run_service = AssemblyRunService(AssemblyRun)
assembly_submission_service = AssemblySubmissionService(AssemblySubmission)
assembly_file_service = AssemblyFileService(AssemblyFile)
assembly_read_service = AssemblyReadService(AssemblyRead)
assembly_stage_run_service = AssemblyStageRunService(AssemblyStageRun)

import json
import os
import uuid
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.experiment import Experiment, ExperimentSubmission
from app.models.project import Project
from app.models.read import Read, ReadSubmission
from app.models.sample import Sample
from app.schemas.bulk_import import BulkImportResponseExperiments
from app.schemas.common import SubmissionStatus
from app.schemas.experiment import ExperimentCreate, ExperimentUpdate
from app.services.base_service import BaseService
from app.utils.mapping import map_to_model_columns, to_bool


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
        bpa_package_id: Optional[str] = None,
    ) -> List[Experiment]:
        """Get experiments with filters."""
        query = db.query(Experiment)
        if sample_id:
            query = query.filter(Experiment.sample_id == sample_id)
        if bpa_package_id:
            query = query.filter(Experiment.bpa_package_id.ilike(f"%{bpa_package_id}%"))
        return query.offset(skip).limit(limit).all()

    # ---------- New business operations (moved from endpoints) ----------

    def list_experiments(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        sample_id: Optional[UUID] = None,
    ) -> List[Experiment]:
        """List experiments with optional sample filter."""
        query = db.query(Experiment)
        if sample_id:
            query = query.filter(Experiment.sample_id == sample_id)
        return query.offset(skip).limit(limit).all()

    @staticmethod
    def _mapping_path() -> str:
        return os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "config",
            "ena-atol-map.json",
        )

    def create_experiment(self, db: Session, *, experiment_in: ExperimentCreate) -> Experiment:
        """Create experiment and corresponding submission with prepared payload."""
        experiment_id = uuid.uuid4()

        # Auto-map fields from Pydantic schema to Experiment columns using shared mapper
        exp_data = experiment_in.model_dump(exclude_unset=True)
        transforms = {"insert_size": (lambda v: str(v) if v is not None else None)}
        inject = {"id": experiment_id}
        experiment_kwargs = map_to_model_columns(
            Experiment,
            exp_data,
            transforms=transforms,
            inject=inject,
        )
        experiment = Experiment(**experiment_kwargs)
        db.add(experiment)

        # Load mapping file and generate prepared payload
        with open(self._mapping_path(), "r") as f:
            ena_atol_map = json.load(f)
        prepared_payload: Dict[str, Any] = {}
        for ena_key, atol_key in ena_atol_map.get("experiment", {}).items():
            if atol_key in exp_data:
                prepared_payload[ena_key] = exp_data[atol_key]

        experiment_submission = ExperimentSubmission(
            experiment_id=experiment_id,
            sample_id=experiment_in.sample_id,
            project_id=exp_data.get("project_id"),
            entity_type_const="experiment",
            prepared_payload=prepared_payload,
            status=SubmissionStatus.DRAFT,
        )
        db.add(experiment_submission)
        db.commit()
        db.refresh(experiment)
        db.refresh(experiment_submission)
        return experiment

    def get_experiment_prepared_payload(
        self, db: Session, *, experiment_id: UUID
    ) -> Optional[ExperimentSubmission]:
        """Return latest ExperimentSubmission for an experiment, if any."""
        submission = (
            db.query(ExperimentSubmission)
            .filter(ExperimentSubmission.experiment_id == experiment_id)
            .order_by(ExperimentSubmission.updated_at.desc())
            .first()
        )
        return submission

    def update_experiment(
        self,
        db: Session,
        *,
        experiment_id: UUID,
        experiment_in: ExperimentUpdate,
    ) -> Optional[Experiment]:
        """Update experiment and manage ExperimentSubmission status transitions."""
        experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
        if not experiment:
            return None

        experiment_data = experiment_in.dict(exclude_unset=True)

        # Load mapping and regenerate prepared payload
        with open(self._mapping_path(), "r") as f:
            ena_atol_map = json.load(f)
        prepared_payload: Dict[str, Any] = {}
        for ena_key, atol_key in ena_atol_map.get("experiment", {}).items():
            if atol_key in experiment_data:
                prepared_payload[ena_key] = experiment_data[atol_key]

        experiment_submission = (
            db.query(ExperimentSubmission)
            .filter(ExperimentSubmission.experiment_id == experiment_id)
            .order_by(ExperimentSubmission.updated_at.desc())
            .first()
        )
        new_experiment_submission: Optional[ExperimentSubmission] = None
        latest_experiment_submission = experiment_submission

        if not latest_experiment_submission:
            new_experiment_submission = ExperimentSubmission(
                experiment_id=experiment_id,
                sample_id=experiment.sample_id,
                project_id=experiment.project_id,
                authority="ENA",
                entity_type_const="experiment",
                prepared_payload=prepared_payload,
                status="draft",
            )
            db.add(new_experiment_submission)
        else:
            if latest_experiment_submission.status == "submitting":
                raise RuntimeError(
                    f"Experiment {experiment_id} is currently being submitted to ENA and cannot be updated."
                )
            elif latest_experiment_submission.status in ("rejected", "replaced"):
                new_experiment_submission = ExperimentSubmission(
                    experiment_id=experiment_id,
                    sample_id=experiment.sample_id,
                    project_id=experiment.project_id,
                    authority=latest_experiment_submission.authority,
                    entity_type_const="experiment",
                    prepared_payload=prepared_payload,
                    response_payload=None,
                    accession=latest_experiment_submission.accession,
                    biosample_accession=latest_experiment_submission.biosample_accession,
                    status="draft",
                )
                db.add(new_experiment_submission)
            elif latest_experiment_submission.status == "accepted":
                # mark old as replaced and create new draft retaining accessions
                latest_experiment_submission.status = "replaced"
                db.add(latest_experiment_submission)
                new_experiment_submission = ExperimentSubmission(
                    experiment_id=experiment_id,
                    sample_id=experiment.sample_id,
                    project_id=experiment.project_id,
                    authority=latest_experiment_submission.authority,
                    entity_type_const="experiment",
                    prepared_payload=prepared_payload,
                    response_payload=None,
                    accession=latest_experiment_submission.accession,
                    biosample_accession=latest_experiment_submission.biosample_accession,
                    status="draft",
                )
                db.add(new_experiment_submission)
            elif latest_experiment_submission.status in ("draft", "ready"):
                latest_experiment_submission.prepared_payload = prepared_payload
                latest_experiment_submission.status = "draft"
                db.add(latest_experiment_submission)

        # Update core experiment fields
        if experiment_in.bpa_package_id is not None:
            experiment.bpa_package_id = experiment_in.bpa_package_id
        if experiment_in.sample_id is not None:
            experiment.sample_id = experiment_in.sample_id
        db.add(experiment)
        db.commit()
        db.refresh(experiment)
        return experiment

    def delete_experiment(self, db: Session, *, experiment_id: UUID) -> Optional[Experiment]:
        """Delete an experiment by ID."""
        experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
        if not experiment:
            return None
        db.delete(experiment)
        db.commit()
        return experiment

    def bulk_import_experiments(
        self,
        db: Session,
        *,
        experiments_data: Dict[str, Dict[str, Any]],
    ) -> BulkImportResponseExperiments:
        """Bulk import experiments; create reads and submission records; return counts and debug info."""
        # Load the ENA-ATOL mapping file
        with open(self._mapping_path(), "r") as f:
            ena_atol_map = json.load(f)

        experiment_mapping = ena_atol_map.get("experiment", {})
        run_mapping = ena_atol_map.get("run", {})

        created_experiments_count = 0
        created_submission_count = 0
        created_reads_count = 0
        skipped_experiments_count = 0
        skipped_reads_count = 0
        errors = []

        # Debug counters
        missing_bpa_sample_id_count = 0
        missing_sample_count = 0
        existing_experiment_count = 0
        missing_required_fields_count = 0

        for package_id, experiment_data in experiments_data.items():
            # Check if experiment already exists
            existing_experiment = (
                db.query(Experiment).filter(Experiment.bpa_package_id == package_id).first()
            )

            if existing_experiment:
                existing_experiment_count += 1
                skipped_experiments_count += 1
                # Still process reads for existing experiment
                experiment_id = existing_experiment.id

                # Find project for read submissions
                project_id = None
                project = db.query(Project).first()
                if project:
                    project_id = project.id

                # Process reads even though experiment exists
                if isinstance(experiment_data.get("runs"), list):
                    for run in experiment_data["runs"]:
                        try:
                            # Validate required fields for read
                            if not run.get("bpa_resource_id"):
                                run_identifier = (
                                    run.get("filename")
                                    or run.get("run_alias")
                                    or run.get("bpa_dataset_id")
                                    or run.get("flowcell_id")
                                    or "unknown"
                                )
                                errors.append(
                                    f"{package_id} / read '{run_identifier}': Missing required field 'bpa_resource_id'"
                                )
                                skipped_reads_count += 1
                                continue

                            # Check if read already exists
                            existing_read = (
                                db.query(Read)
                                .filter(Read.bpa_resource_id == run.get("bpa_resource_id"))
                                .first()
                            )

                            if existing_read:
                                skipped_reads_count += 1
                                continue

                            read_id = uuid.uuid4()
                            transforms = {"optional_file": to_bool}
                            inject = {"id": read_id, "experiment_id": experiment_id}
                            read_kwargs = map_to_model_columns(
                                Read,
                                run,
                                transforms=transforms,
                                inject=inject,
                            )
                            read = Read(**read_kwargs)
                            db.add(read)
                            created_reads_count += 1

                            run_prepared_payload: Dict[str, Any] = {}
                            for ena_key, atol_key in run_mapping.items():
                                if atol_key in run:
                                    run_prepared_payload[ena_key] = run[atol_key]

                            read_submission = ReadSubmission(
                                id=uuid.uuid4(),
                                read_id=read.id,
                                experiment_id=experiment_id,
                                project_id=project_id,
                                authority="ENA",
                                entity_type_const="read",
                                prepared_payload=run_prepared_payload,
                            )
                            db.add(read_submission)
                            created_submission_count += 1
                        except Exception as e:
                            # Try to get the most identifying information from the run
                            run_identifier = (
                                run.get("filename")
                                or run.get("run_alias")
                                or run.get("bpa_dataset_id")
                                or run.get("flowcell_id")
                                or "unknown"
                            )
                            errors.append(f"{package_id} / read '{run_identifier}': {str(e)}")
                            skipped_reads_count += 1

                    # Commit reads for existing experiment
                    try:
                        db.commit()
                    except Exception as e:
                        errors.append(f"{package_id}: Failed to commit reads - {str(e)}")
                        db.rollback()

                continue

            bpa_sample_id = experiment_data.get("bpa_sample_id")
            if not bpa_sample_id:
                missing_bpa_sample_id_count += 1
                errors.append(f"{package_id}: Missing required field 'bpa_sample_id'")
                skipped_experiments_count += 1
                # Count reads that would have been created
                if isinstance(experiment_data.get("runs"), list):
                    skipped_reads_count += len(experiment_data["runs"])
                continue

            sample = db.query(Sample).filter(Sample.bpa_sample_id == bpa_sample_id).first()
            if not sample:
                missing_sample_count += 1
                errors.append(
                    f"{package_id}: Sample not found with bpa_sample_id '{bpa_sample_id}'"
                )
                skipped_experiments_count += 1
                # Count reads that would have been created
                if isinstance(experiment_data.get("runs"), list):
                    skipped_reads_count += len(experiment_data["runs"])
                continue

            if not experiment_data.get("bpa_library_id"):
                missing_required_fields_count += 1
                errors.append(f"{package_id}: Missing required field 'bpa_library_id'")
                skipped_experiments_count += 1
                # Count reads that would have been created
                if isinstance(experiment_data.get("runs"), list):
                    skipped_reads_count += len(experiment_data["runs"])
                continue

            try:
                # Create experiment
                experiment_id = uuid.uuid4()
                sample_id = sample.id
                aliases = {"GAL": "gal", "extraction_protocol_DOI": "extraction_protocol_doi"}
                transforms = {"insert_size": (lambda v: str(v) if v is not None else None)}
                inject = {"id": experiment_id, "sample_id": sample_id, "bpa_package_id": package_id}
                experiment_kwargs = map_to_model_columns(
                    Experiment,
                    experiment_data,
                    aliases=aliases,
                    transforms=transforms,
                    inject=inject,
                )
                experiment = Experiment(**experiment_kwargs)
                db.add(experiment)

                # Find a project (fallback to any project for now)
                project_id = None
                project = db.query(Project).first()
                if project:
                    project_id = project.id

                # Build prepared payload for experiment submission
                prepared_payload: Dict[str, Any] = {}
                for ena_key, atol_key in experiment_mapping.items():
                    if atol_key in experiment_data:
                        prepared_payload[ena_key] = experiment_data[atol_key]

                experiment_submission = ExperimentSubmission(
                    id=uuid.uuid4(),
                    experiment_id=experiment_id,
                    sample_id=sample_id,
                    project_id=project_id,
                    authority="ENA",
                    entity_type_const="experiment",
                    prepared_payload=prepared_payload,
                )
                db.add(experiment_submission)

                # Create reads and read submissions
                if isinstance(experiment_data.get("runs"), list):
                    for run in experiment_data["runs"]:
                        try:
                            # Validate required fields for read
                            if not run.get("bpa_resource_id"):
                                run_identifier = (
                                    run.get("filename")
                                    or run.get("run_alias")
                                    or run.get("bpa_dataset_id")
                                    or run.get("flowcell_id")
                                    or "unknown"
                                )
                                errors.append(
                                    f"{package_id} / read '{run_identifier}': Missing required field 'bpa_resource_id'"
                                )
                                skipped_reads_count += 1
                                continue

                            read_id = uuid.uuid4()
                            transforms = {"optional_file": to_bool}
                            inject = {"id": read_id, "experiment_id": experiment_id}
                            read_kwargs = map_to_model_columns(
                                Read,
                                run,
                                transforms=transforms,
                                inject=inject,
                            )
                            read = Read(**read_kwargs)
                            db.add(read)
                            created_reads_count += 1

                            run_prepared_payload: Dict[str, Any] = {}
                            for ena_key, atol_key in run_mapping.items():
                                if atol_key in run:
                                    run_prepared_payload[ena_key] = run[atol_key]

                            read_submission = ReadSubmission(
                                id=uuid.uuid4(),
                                read_id=read.id,
                                experiment_id=experiment_id,
                                project_id=project_id,
                                authority="ENA",
                                entity_type_const="read",
                                prepared_payload=run_prepared_payload,
                            )
                            db.add(read_submission)
                            created_submission_count += 1
                        except Exception as e:
                            # Try to get the most identifying information from the run
                            run_identifier = (
                                run.get("filename")
                                or run.get("run_alias")
                                or run.get("bpa_dataset_id")
                                or run.get("flowcell_id")
                                or "unknown"
                            )
                            errors.append(f"{package_id} / read '{run_identifier}': {str(e)}")
                            skipped_reads_count += 1

                db.commit()
                created_experiments_count += 1
                created_submission_count += 1
            except Exception as e:
                errors.append(f"{package_id}: {str(e)}")
                db.rollback()
                skipped_experiments_count += 1

        return BulkImportResponseExperiments(
            created_experiment_count=created_experiments_count,
            skipped_experiment_count=skipped_experiments_count,
            created_reads_count=created_reads_count,
            skipped_reads_count=skipped_reads_count,
            message=(
                f"Experiments: {created_experiments_count} created, {skipped_experiments_count} skipped. "
                f"Reads: {created_reads_count} created, {skipped_reads_count} skipped. "
                f"Submission records: {created_submission_count} created."
            ),
            errors=errors if errors else None,
            debug={
                "missing_bpa_sample_id": missing_bpa_sample_id_count,
                "missing_sample": missing_sample_count,
                "existing_experiment": existing_experiment_count,
                "missing_required_fields": missing_required_fields_count,
            },
        )


class ExperimentSubmissionService(
    BaseService[ExperimentSubmission, ExperimentCreate, ExperimentUpdate]
):
    """Service for ExperimentSubmission operations."""

    def get_by_experiment_id(self, db: Session, experiment_id: UUID) -> List[ExperimentSubmission]:
        """Get submission experiments by experiment ID."""
        return (
            db.query(ExperimentSubmission)
            .filter(ExperimentSubmission.experiment_id == experiment_id)
            .all()
        )

    def get_by_sample_id(self, db: Session, sample_id: UUID) -> List[ExperimentSubmission]:
        """Get submission experiments by sample ID."""
        return (
            db.query(ExperimentSubmission).filter(ExperimentSubmission.sample_id == sample_id).all()
        )

    def get_by_project_id(self, db: Session, project_id: UUID) -> List[ExperimentSubmission]:
        """Get submission experiments by project ID."""
        return (
            db.query(ExperimentSubmission)
            .filter(ExperimentSubmission.project_id == project_id)
            .all()
        )

    def get_by_accession(self, db: Session, accession: str) -> Optional[ExperimentSubmission]:
        """Get submission experiment by accession."""
        return (
            db.query(ExperimentSubmission)
            .filter(ExperimentSubmission.accession == accession)
            .first()
        )


# ExperimentFetched model has been removed from the schema


experiment_service = ExperimentService(Experiment)
experiment_submission_service = ExperimentSubmissionService(ExperimentSubmission)

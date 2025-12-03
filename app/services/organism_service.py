from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.organism import Organism
from app.schemas.organism import OrganismCreate, OrganismUpdate
from app.services.base_service import BaseService
from app.models.sample import Sample, SampleSubmission
from app.models.experiment import Experiment, ExperimentSubmission
from app.models.read import Read, ReadSubmission
from app.models.project import Project, ProjectSubmission
from app.schemas.bulk_import import BulkImportResponse
from app.schemas.aggregate import OrganismSubmissionJsonResponse


class OrganismService(BaseService[Organism, OrganismCreate, OrganismUpdate]):
    """Service for Organism operations."""
    
    def get_by_scientific_name(self, db: Session, scientific_name: str) -> Optional[Organism]:
        """Get organism by scientific name."""
        return db.query(Organism).filter(Organism.scientific_name == scientific_name).first()
    
    def get_by_tax_id(self, db: Session, tax_id: str) -> Optional[Organism]:
        """Get organism by taxon ID."""
        return db.query(Organism).filter(Organism.tax_id == tax_id).first()
    
    def get_by_grouping_key(self, db: Session, grouping_key: str) -> Optional[Organism]:
        """Get organism by grouping_key."""
        return db.query(Organism).filter(Organism.grouping_key == grouping_key).first()
    
    def get_multi_with_filters(
        self, 
        db: Session, 
        *, 
        skip: int = 0, 
        limit: int = 100,
        scientific_name: Optional[str] = None,
        tax_id: Optional[str] = None,
        grouping_key: Optional[str] = None
    ) -> List[Organism]:
        """Get organisms with filters."""
        query = db.query(Organism)
        if scientific_name:
            query = query.filter(Organism.scientific_name.ilike(f"%{scientific_name}%"))
        if tax_id:
            query = query.filter(Organism.tax_id == tax_id)
        if grouping_key:
            query = query.filter(Organism.grouping_key == grouping_key)
        return query.offset(skip).limit(limit).all()

    # ---------- New business operations (moved from endpoints) ----------

    def list_organisms(self, db: Session, *, skip: int = 0, limit: int = 100) -> List[Organism]:
        """List organisms with pagination."""
        return db.query(Organism).offset(skip).limit(limit).all()

    @staticmethod
    def _sa_obj_to_dict(obj: Any) -> Dict[str, Any]:
        """Serialize all SQLAlchemy column fields for a model instance."""
        return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}

    def get_experiments_for_organism(
        self,
        db: Session,
        *,
        grouping_key: str,
        include_reads: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Return all experiments for the organism, and optionally all reads for each experiment.

        Returns None if the organism cannot be found.
        """
        organism = db.query(Organism).filter(Organism.grouping_key == grouping_key).first()
        if not organism:
            return None

        # Find all samples for this organism
        samples = db.query(Sample.id).filter(Sample.organism_key == grouping_key).all()
        sample_ids = [sid for (sid,) in samples]

        # Load experiments
        experiments: List[Experiment] = []
        if sample_ids:
            experiments = db.query(Experiment).filter(Experiment.sample_id.in_(sample_ids)).all()

        # Build response
        if not include_reads:
            exp_list = [self._sa_obj_to_dict(e) for e in experiments]
            return {"grouping_key": grouping_key, "experiments": exp_list}

        # include_reads = True
        exp_ids = [e.id for e in experiments]
        reads_by_exp: Dict[str, List[Dict[str, Any]]] = {}
        if exp_ids:
            reads = db.query(Read).filter(Read.experiment_id.in_(exp_ids)).all()
            for r in reads:
                key = str(r.experiment_id) if r.experiment_id else "null"
                if key not in reads_by_exp:
                    reads_by_exp[key] = []
                reads_by_exp[key].append(self._sa_obj_to_dict(r))

        exp_with_reads: List[Dict[str, Any]] = []
        for e in experiments:
            item = self._sa_obj_to_dict(e)
            item["reads"] = reads_by_exp.get(str(e.id), [])
            exp_with_reads.append(item)

        return {
            "grouping_key": grouping_key,
            "experiments": exp_with_reads,
        }

    def get_organism_prepared_payload(
        self,
        db: Session,
        *,
        grouping_key: str,
    ) -> Optional[OrganismSubmissionJsonResponse]:
        """Get all prepared_payload data for samples, experiments, and reads for a grouping_key.

        Returns None if the organism cannot be found.
        """
        organism = db.query(Organism).filter(Organism.grouping_key == grouping_key).first()
        if not organism:
            return None

        response = OrganismSubmissionJsonResponse(
            grouping_key=organism.grouping_key,
            tax_id=organism.tax_id,
            scientific_name=organism.scientific_name,
            common_name=organism.common_name,
            common_name_source=organism.common_name_source,
            samples=[],
            experiments=[],
            reads=[],
        )

        # Samples
        samples = db.query(Sample).filter(Sample.organism_key == organism.grouping_key).all()
        sample_ids = [sample.id for sample in samples]

        if sample_ids:
            sample_submission_records = (
                db.query(SampleSubmission).filter(SampleSubmission.sample_id.in_(sample_ids)).all()
            )
            response.samples = sample_submission_records  # Keep ORM records to mirror previous behavior

        # Experiments and reads
        if sample_ids:
            experiments = db.query(Experiment).filter(Experiment.sample_id.in_(sample_ids)).all()
            experiment_ids = [experiment.id for experiment in experiments]

            if experiment_ids:
                experiment_submission_records = (
                    db.query(ExperimentSubmission)
                    .filter(ExperimentSubmission.experiment_id.in_(experiment_ids))
                    .all()
                )
                response.experiments = experiment_submission_records

                reads = db.query(Read).filter(Read.experiment_id.in_(experiment_ids)).all()
                read_ids = [read.id for read in reads]

                if read_ids:
                    read_submission_records = (
                        db.query(ReadSubmission).filter(ReadSubmission.read_id.in_(read_ids)).all()
                    )
                    response.reads = read_submission_records

        return response

    def create_organism(self, db: Session, *, organism_in: OrganismCreate) -> Organism:
        """Create a new organism and draft projects + submissions."""
        common_name = organism_in.common_name
        common_name_source = organism_in.common_name_source
        if common_name and not common_name_source:
            common_name_source = "BPA"

        organism = Organism(
            grouping_key=organism_in.grouping_key,
            tax_id=organism_in.tax_id,
            scientific_name=organism_in.scientific_name,
            common_name=common_name,
            common_name_source=common_name_source,
            taxonomy_lineage_json=organism_in.taxonomy_lineage_json,
            bpa_json=organism_in.dict(exclude_unset=True),
        )
        db.add(organism)
        try:
            root_project = Project(
                organism_key=organism.grouping_key,
                project_type="root",
                study_type="Whole Genome Sequencing",
                project_accession=None,
                alias=f"{organism_in.scientific_name} genome assembly and related data",
                title=f"{organism_in.scientific_name}",
                description=(
                    f"Genome assemblies and related data for the organism {organism_in.scientific_name}, "
                    f"brokered on behalf of the Australian Tree of Life (AToL) project"
                ),
                centre_name="Australian Tree of Life (AToL)",
                study_attributes=None,
                submitted_at=None,
                status="draft",
                authority="ENA",
            )
            genomic_data_project = Project(
                organism_key=organism.grouping_key,
                project_type="genomic_data",
                study_type="Whole Genome Sequencing",
                project_accession=None,
                alias=f"Genomic data for {organism_in.scientific_name}",
                title=f"{organism_in.scientific_name} - genomic data",
                description=(
                    f"Genomic data for the organism {organism_in.scientific_name}, brokered on behalf of the "
                    f"Australian Tree of Life (AToL) project"
                ),
                centre_name="Australian Tree of Life (AToL)",
                study_attributes=None,
                submitted_at=None,
                status="draft",
                authority="ENA",
            )
            db.add(root_project)
            db.add(genomic_data_project)
            db.flush()  # Ensure project IDs

            root_payload = {
                "organism_key": root_project.organism_key,
                "project_type": root_project.project_type,
                "study_type": root_project.study_type,
                "alias": root_project.alias,
                "title": root_project.title,
                "description": root_project.description,
                "centre_name": root_project.centre_name,
                "study_attributes": root_project.study_attributes,
            }
            genomic_payload = {
                "organism_key": genomic_data_project.organism_key,
                "project_type": genomic_data_project.project_type,
                "study_type": genomic_data_project.study_type,
                "alias": genomic_data_project.alias,
                "title": genomic_data_project.title,
                "description": genomic_data_project.description,
                "centre_name": genomic_data_project.centre_name,
                "study_attributes": genomic_data_project.study_attributes,
            }
            db.add(ProjectSubmission(project_id=root_project.id, prepared_payload=root_payload))
            db.add(ProjectSubmission(project_id=genomic_data_project.id, prepared_payload=genomic_payload))
        except Exception:
            db.rollback()
            raise

        db.commit()
        db.refresh(organism)
        return organism

    def update_organism(
        self,
        db: Session,
        *,
        grouping_key: str,
        organism_in: OrganismUpdate,
    ) -> Optional[Organism]:
        """Update an organism by grouping_key, mirroring previous behavior."""
        organism = db.query(Organism).filter(Organism.grouping_key == grouping_key).first()
        if not organism:
            return None

        new_bpa_json: Dict[str, Any] = organism.bpa_json or {}
        update_data = organism_in.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(organism, field, value)
            if field == "common_name_source":
                continue
            # Persist change into bpa_json snapshot
            new_bpa_json[field] = value

        organism.bpa_json = new_bpa_json
        db.add(organism)
        db.commit()
        db.refresh(organism)
        return organism

    def delete_organism(self, db: Session, *, grouping_key: str) -> Optional[Organism]:
        """Delete an organism by grouping_key."""
        organism = db.query(Organism).filter(Organism.grouping_key == grouping_key).first()
        if not organism:
            return None
        db.delete(organism)
        db.commit()
        return organism

    def bulk_import_organisms(
        self,
        db: Session,
        *,
        organisms_data: Dict[str, Dict[str, Any]],
    ) -> BulkImportResponse:
        """Bulk import organisms from a dictionary keyed by organism_grouping_key."""
        created_count = 0
        skipped_count = 0

        for organism_grouping_key, organism_data in organisms_data.items():
            # Extract tax_id from the organism data
            if "taxon_id" in organism_data:
                tax_id = organism_data["taxon_id"]
            else:
                skipped_count += 1
                continue

            if "organism_grouping_key" not in organism_data:
                skipped_count += 1
                continue

            # Check if organism already exists by grouping key
            existing = db.query(Organism).filter(Organism.grouping_key == organism_grouping_key).first()
            if existing:
                skipped_count += 1
                continue

            # Validate minimal requirements
            scientific_name = organism_data.get("scientific_name")
            if not scientific_name:
                skipped_count += 1
                continue

            try:
                common_name = organism_data.get("common_name", None)
                common_name_source = (
                    organism_data.get("common_name_source", "BPA") if common_name is not None else None
                )
                organism = Organism(
                    grouping_key=organism_grouping_key,
                    tax_id=tax_id,
                    common_name=common_name,
                    common_name_source=common_name_source,
                    scientific_name=scientific_name,
                    bpa_json=organism_data,
                )
                root_project = Project(
                    organism_key=organism.grouping_key,
                    project_type="root",
                    study_type="Whole Genome Sequencing",
                    project_accession=None,
                    alias=f"{organism.scientific_name} genome assembly and related data",
                    title=f"{organism.scientific_name}",
                    description=(
                        f"Genome assemblies and related data for the organism {organism.scientific_name}, "
                        f"brokered on behalf of the Australian Tree of Life (AToL) project"
                    ),
                    centre_name="Australian Tree of Life (AToL)",
                    study_attributes=None,
                    submitted_at=None,
                    status="draft",
                    authority="ENA",
                )
                genomic_data_project = Project(
                    organism_key=organism.grouping_key,
                    project_type="genomic_data",
                    study_type="Whole Genome Sequencing",
                    project_accession=None,
                    alias=f"Genomic data for {organism.scientific_name}",
                    title=f"{organism.scientific_name} - genomic data",
                    description=(
                        f"Genomic data for the organism {organism.scientific_name}, brokered on behalf of the Australian Tree of Life (AToL) project"
                    ),
                    centre_name="Australian Tree of Life (AToL)",
                    study_attributes=None,
                    submitted_at=None,
                    status="draft",
                    authority="ENA",
                )
                db.add(organism)
                db.add(root_project)
                db.add(genomic_data_project)
                db.flush()

                root_payload = {
                    "organism_key": root_project.organism_key,
                    "project_type": root_project.project_type,
                    "study_type": root_project.study_type,
                    "alias": root_project.alias,
                    "title": root_project.title,
                    "description": root_project.description,
                    "centre_name": root_project.centre_name,
                    "study_attributes": root_project.study_attributes,
                }
                genomic_payload = {
                    "organism_key": genomic_data_project.organism_key,
                    "project_type": genomic_data_project.project_type,
                    "study_type": genomic_data_project.study_type,
                    "alias": genomic_data_project.alias,
                    "title": genomic_data_project.title,
                    "description": genomic_data_project.description,
                    "centre_name": genomic_data_project.centre_name,
                    "study_attributes": genomic_data_project.study_attributes,
                }
                db.add(ProjectSubmission(project_id=root_project.id, prepared_payload=root_payload))
                db.add(ProjectSubmission(project_id=genomic_data_project.id, prepared_payload=genomic_payload))
                db.commit()
                created_count += 1
            except Exception:
                db.rollback()
                skipped_count += 1

        return BulkImportResponse(
            created_count=created_count,
            skipped_count=skipped_count,
            message=f"Organism import complete. Created: {created_count}, Skipped: {skipped_count}",
        )


organism_service = OrganismService(Organism)

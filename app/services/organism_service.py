from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session, selectinload

from app.models.experiment import Experiment, ExperimentSubmission
from app.models.organism import Organism
from app.models.project import Project, ProjectSubmission
from app.models.qc_read import QcRead, QcReadSubmission
from app.models.read import Read
from app.models.sample import Sample, SampleSubmission
from app.schemas.aggregate import OrganismSubmissionJsonResponse
from app.schemas.bulk_import import BulkImportResponse
from app.schemas.organism import OrganismCreate, OrganismUpdate
from app.services.base_service import BaseService


class OrganismService(BaseService[Organism, OrganismCreate, OrganismUpdate]):
    """Service for Organism operations."""

    def get_by_scientific_name(self, db: Session, scientific_name: str) -> Optional[Organism]:
        """Get organism by scientific name."""
        return db.query(Organism).filter(Organism.scientific_name == scientific_name).first()

    def get_by_taxon_id(self, db: Session, taxon_id: int) -> Optional[Organism]:
        """Get organism by taxon ID."""
        return db.query(Organism).filter(Organism.taxon_id == taxon_id).first()

    def get_multi_with_filters(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        scientific_name: Optional[str] = None,
        taxon_id: Optional[int] = None,
    ) -> List[Organism]:
        """Get organisms with filters."""
        query = db.query(Organism)
        if scientific_name:
            query = query.filter(Organism.scientific_name.ilike(f"%{scientific_name}%"))
        if taxon_id is not None:
            query = query.filter(Organism.taxon_id == taxon_id)
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
        taxon_id: int,
        include_reads: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Return all experiments for the organism, and optionally all reads for each experiment.

        Returns None if the organism cannot be found.
        """
        organism = db.query(Organism).filter(Organism.taxon_id == taxon_id).first()
        if not organism:
            return None

        # Find all samples for this organism
        samples = db.query(Sample.id).filter(Sample.taxon_id == taxon_id).all()
        sample_ids = [sid for (sid,) in samples]

        # Load experiments (eager load reads when requested)
        experiments: List[Experiment] = []
        if sample_ids:
            query = db.query(Experiment).filter(Experiment.sample_id.in_(sample_ids))
            if include_reads:
                query = query.options(selectinload(Experiment.reads))
            experiments = query.all()

        # Build response
        if not include_reads:
            exp_list = [self._sa_obj_to_dict(e) for e in experiments]
            return {"taxon_id": taxon_id, "experiments": exp_list}

        # include_reads = True
        reads_by_exp: Dict[str, List[Dict[str, Any]]] = {}
        for e in experiments:
            if not e.reads:
                continue
            reads_by_exp[str(e.id)] = [self._sa_obj_to_dict(r) for r in e.reads]

        exp_with_reads: List[Dict[str, Any]] = []
        for e in experiments:
            item = self._sa_obj_to_dict(e)
            item["reads"] = reads_by_exp.get(str(e.id), [])
            exp_with_reads.append(item)

        return {
            "taxon_id": taxon_id,
            "experiments": exp_with_reads,
        }

    def get_organism_prepared_payload(
        self,
        db: Session,
        *,
        taxon_id: int,
    ) -> Optional[OrganismSubmissionJsonResponse]:
        """Get all prepared_payload data for samples, experiments, and reads for a taxon_id.

        Returns None if the organism cannot be found.
        """
        organism = db.query(Organism).filter(Organism.taxon_id == taxon_id).first()
        if not organism:
            return None

        response = OrganismSubmissionJsonResponse(
            taxon_id=organism.taxon_id,
            scientific_name=organism.scientific_name,
            samples=[],
            experiments=[],
            reads=[],
        )

        # Samples
        samples = db.query(Sample).filter(Sample.taxon_id == organism.taxon_id).all()
        sample_ids = [sample.id for sample in samples]

        if sample_ids:
            sample_submission_records = (
                db.query(SampleSubmission).filter(SampleSubmission.sample_id.in_(sample_ids)).all()
            )
            response.samples = (
                sample_submission_records  # Keep ORM records to mirror previous behavior
            )

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

                qc_reads = db.query(QcRead).filter(QcRead.experiment_id.in_(experiment_ids)).all()
                qc_read_ids = [qr.id for qr in qc_reads]

                if qc_read_ids:
                    qc_read_submission_records = (
                        db.query(QcReadSubmission)
                        .filter(QcReadSubmission.qc_read_id.in_(qc_read_ids))
                        .all()
                    )
                    response.reads = qc_read_submission_records

        return response

    def create_organism(self, db: Session, *, organism_in: OrganismCreate) -> Organism:
        """Create a new organism and draft projects + submissions."""
        organism_label = organism_in.scientific_name or str(organism_in.taxon_id)
        organism = Organism(
            taxon_id=organism_in.taxon_id,
            scientific_name=organism_in.scientific_name,
            common_name=organism_in.common_name,
            common_name_source=organism_in.common_name_source,
            genus=organism_in.genus,
            species=organism_in.species,
            infraspecific_epithet=organism_in.infraspecific_epithet,
            culture_or_strain_id=organism_in.culture_or_strain_id,
            authority=organism_in.authority,
            atol_scientific_name=organism_in.atol_scientific_name,
            tax_string=organism_in.tax_string,
            ncbi_order=organism_in.ncbi_order,
            ncbi_family=organism_in.ncbi_family,
            busco_dataset_name=organism_in.busco_dataset_name,
            taxonomy_lineage_json=organism_in.taxonomy_lineage_json,
            bpa_json=organism_in.model_dump(exclude_unset=True),
        )
        db.add(organism)
        try:
            root_project = Project(
                taxon_id=organism.taxon_id,
                project_type="root",
                study_type="Whole Genome Sequencing",
                project_accession=None,
                alias=f"{organism_label} genome assembly and related data",
                title=f"{organism_label}",
                description=(
                    f"Genome assemblies and related data for the organism {organism_label}, "
                    f"brokered on behalf of the Australian Tree of Life (AToL) project"
                ),
                centre_name="Australian Tree of Life (AToL)",
                study_attributes=None,
                submitted_at=None,
                status="draft",
                authority="ENA",
            )
            genomic_data_project = Project(
                taxon_id=organism.taxon_id,
                project_type="genomic_data",
                study_type="Whole Genome Sequencing",
                project_accession=None,
                alias=f"Genomic data for {organism_label}",
                title=f"{organism_label} - genomic data",
                description=(
                    f"Genomic data for the organism {organism_label}, brokered on behalf of the "
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
                "taxon_id": root_project.taxon_id,
                "project_type": root_project.project_type,
                "study_type": root_project.study_type,
                "alias": root_project.alias,
                "title": root_project.title,
                "description": root_project.description,
                "centre_name": root_project.centre_name,
                "study_attributes": root_project.study_attributes,
            }
            genomic_payload = {
                "taxon_id": genomic_data_project.taxon_id,
                "project_type": genomic_data_project.project_type,
                "study_type": genomic_data_project.study_type,
                "alias": genomic_data_project.alias,
                "title": genomic_data_project.title,
                "description": genomic_data_project.description,
                "centre_name": genomic_data_project.centre_name,
                "study_attributes": genomic_data_project.study_attributes,
            }
            db.add(ProjectSubmission(project_id=root_project.id, prepared_payload=root_payload))
            db.add(
                ProjectSubmission(
                    project_id=genomic_data_project.id, prepared_payload=genomic_payload
                )
            )
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
        taxon_id: int,
        organism_in: OrganismUpdate,
    ) -> Optional[Organism]:
        """Update an organism by taxon_id."""
        organism = db.query(Organism).filter(Organism.taxon_id == taxon_id).first()
        if not organism:
            return None
        non_bpa_fields = [
            "ncbi_order",
            "ncbi_family",
            "busco_dataset_name",
            "common_name",
            "common_name_source",
            "tax_string",
        ]
        new_bpa_json: Dict[str, Any] = organism.bpa_json or {}
        update_data = organism_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(organism, field, value)
            if field in non_bpa_fields:
                continue
            # Persist change into bpa_json snapshot
            new_bpa_json[field] = value

        organism.bpa_json = new_bpa_json
        db.add(organism)
        db.commit()
        db.refresh(organism)
        return organism

    def delete_organism(self, db: Session, *, taxon_id: int) -> Optional[Organism]:
        """Delete an organism by taxon_id."""
        organism = db.query(Organism).filter(Organism.taxon_id == taxon_id).first()
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
        """Bulk import organisms from a dictionary keyed by taxon_id."""
        created_count = 0
        skipped_count = 0
        errors = []

        for taxon_key, organism_data in organisms_data.items():
            try:
                taxon_id = organism_data.get("taxon_id", taxon_key)
                if taxon_id is None:
                    errors.append(f"{taxon_key}: Missing required field 'taxon_id'")
                    skipped_count += 1
                    continue
                taxon_id = int(taxon_id)

                existing = db.query(Organism).filter(Organism.taxon_id == taxon_id).first()
                if existing:
                    errors.append(f"{taxon_key}: Organism already exists")
                    skipped_count += 1
                    continue

                scientific_name = organism_data.get("scientific_name")
                organism_label = scientific_name or str(taxon_id)

                # Create organism and projects
                organism = Organism(
                    taxon_id=taxon_id,
                    scientific_name=scientific_name,
                    genus=organism_data.get("genus"),
                    species=organism_data.get("species"),
                    infraspecific_epithet=organism_data.get("infraspecific_epithet"),
                    culture_or_strain_id=organism_data.get("culture_or_strain_id"),
                    authority=organism_data.get("authority"),
                    atol_scientific_name=organism_data.get("atol_scientific_name"),
                    tax_string=organism_data.get("tax_string"),
                    ncbi_order=organism_data.get("ncbi_order"),
                    ncbi_family=organism_data.get("ncbi_family"),
                    busco_dataset_name=organism_data.get("busco_dataset_name"),
                    bpa_json=organism_data,
                )
                root_project = Project(
                    taxon_id=organism.taxon_id,
                    project_type="root",
                    study_type="Whole Genome Sequencing",
                    project_accession=None,
                    alias=f"{organism_label} genome assembly and related data",
                    title=f"{organism_label}",
                    description=(
                        f"Genome assemblies and related data for the organism {organism_label}, "
                        f"brokered on behalf of the Australian Tree of Life (AToL) project"
                    ),
                    centre_name="Australian Tree of Life (AToL)",
                    study_attributes=None,
                    submitted_at=None,
                    status="draft",
                    authority="ENA",
                )
                genomic_data_project = Project(
                    taxon_id=organism.taxon_id,
                    project_type="genomic_data",
                    study_type="Whole Genome Sequencing",
                    project_accession=None,
                    alias=f"Genomic data for {organism_label}",
                    title=f"{organism_label} - genomic data",
                    description=(
                        f"Genomic data for the organism {organism_label}, brokered on behalf of the Australian Tree of Life (AToL) project"
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
                    "taxon_id": root_project.taxon_id,
                    "project_type": root_project.project_type,
                    "study_type": root_project.study_type,
                    "alias": root_project.alias,
                    "title": root_project.title,
                    "description": root_project.description,
                    "centre_name": root_project.centre_name,
                    "study_attributes": root_project.study_attributes,
                }
                genomic_payload = {
                    "taxon_id": genomic_data_project.taxon_id,
                    "project_type": genomic_data_project.project_type,
                    "study_type": genomic_data_project.study_type,
                    "alias": genomic_data_project.alias,
                    "title": genomic_data_project.title,
                    "description": genomic_data_project.description,
                    "centre_name": genomic_data_project.centre_name,
                    "study_attributes": genomic_data_project.study_attributes,
                }
                db.add(ProjectSubmission(project_id=root_project.id, prepared_payload=root_payload))
                db.add(
                    ProjectSubmission(
                        project_id=genomic_data_project.id, prepared_payload=genomic_payload
                    )
                )
                db.commit()
                created_count += 1
            except Exception as e:
                errors.append(f"{taxon_key}: {str(e)}")
                db.rollback()
                skipped_count += 1

        return BulkImportResponse(
            created_count=created_count,
            skipped_count=skipped_count,
            message=f"Organism import complete. Created: {created_count}, Skipped: {skipped_count}",
            errors=errors if errors else None,
        )


organism_service = OrganismService(Organism)

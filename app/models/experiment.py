import uuid

from sqlalchemy import Column, DateTime, ForeignKey, ForeignKeyConstraint, Text, func
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import backref, relationship

from app.db.session import Base


class Experiment(Base):
    """
    Experiment model for storing experiment information.

    This model corresponds to the 'experiment' table in the database.
    """

    __tablename__ = "experiment"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sample_id = Column(
        UUID(as_uuid=True), ForeignKey("sample.id", ondelete="CASCADE"), nullable=False
    )
    bpa_package_id = Column(Text, unique=True, nullable=False)
    design_description = Column(Text, nullable=True)
    bpa_library_id = Column(Text, nullable=True)
    library_strategy = Column(Text, nullable=True)
    library_source = Column(Text, nullable=True)
    insert_size = Column(Text, nullable=True)
    library_construction_protocol = Column(Text, nullable=True)
    library_selection = Column(Text, nullable=True)
    library_layout = Column(Text, nullable=True)
    instrument_model = Column(Text, nullable=True)
    platform = Column(Text, nullable=True)
    material_extracted_by = Column(Text, nullable=True)
    library_prepared_by = Column(Text, nullable=True)
    sequencing_kit = Column(Text, nullable=True)
    flowcell_type = Column(Text, nullable=True)
    base_caller_model = Column(Text, nullable=True)
    data_owner = Column(Text, nullable=True)
    project_collaborators = Column(Text, nullable=True)
    extraction_method = Column(Text, nullable=True)
    nucleic_acid_treatment = Column(Text, nullable=True)
    extraction_protocol_doi = Column(Text, nullable=True)
    nucleic_acid_conc = Column(Text, nullable=True)
    nucleic_acid_volume = Column(Text, nullable=True)
    gal = Column(Text, nullable=True)
    raw_data_release_date = Column(Text, nullable=True)
    # bpa_json = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    sample = relationship(
        "Sample", backref=backref("exp_sample_records", cascade="all, delete-orphan")
    )


class ExperimentSubmission(Base):
    """
    ExperimentSubmission model for storing experiment data staged for submission to ENA.

    This model corresponds to the 'experiment_submission' table in the database.
    """

    __tablename__ = "experiment_submission"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    experiment_id = Column(
        UUID(as_uuid=True), ForeignKey("experiment.id", ondelete="CASCADE"), nullable=True
    )
    authority = Column(
        SQLAlchemyEnum("ENA", "NCBI", "DDBJ", name="authority_type"), nullable=False, default="ENA"
    )
    status = Column(
        SQLAlchemyEnum(
            "draft",
            "ready",
            "submitting",
            "accepted",
            "rejected",
            "replaced",
            name="submission_status",
        ),
        nullable=False,
        default="draft",
    )

    sample_id = Column(
        UUID(as_uuid=True), ForeignKey("sample.id", ondelete="SET NULL"), nullable=False
    )
    project_id = Column(
        UUID(as_uuid=True), ForeignKey("project.id", ondelete="SET NULL"), nullable=True
    )

    project_accession = Column(Text, nullable=True)
    sample_accession = Column(Text, nullable=True)

    prepared_payload = Column(JSONB, nullable=True)
    response_payload = Column(JSONB, nullable=True)
    accession = Column(Text, nullable=True)

    # Constant to help the composite FK
    entity_type_const = Column(
        Text, nullable=False, default="experiment", server_default="experiment"
    )
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Broker lease/claim fields
    attempt_id = Column(UUID(as_uuid=True), nullable=True)
    finalised_attempt_id = Column(UUID(as_uuid=True), nullable=True)
    lock_acquired_at = Column(DateTime(timezone=True), nullable=True)
    lock_expires_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    experiment = relationship(
        "Experiment", backref=backref("exp_submission_records", cascade="all, delete-orphan")
    )
    sample = relationship(
        "Sample", backref=backref("exp_sample_submission_records", cascade="all, delete-orphan")
    )
    project = relationship(
        "Project", backref=backref("exp_project_submission_records", cascade="all, delete-orphan")
    )

    # Table constraints
    __table_args__ = (
        # Foreign key constraint for accession registry (self)
        ForeignKeyConstraint(
            ["accession", "authority", "entity_type_const", "experiment_id"],
            [
                "accession_registry.accession",
                "accession_registry.authority",
                "accession_registry.entity_type",
                "accession_registry.entity_id",
            ],
            name="fk_self_accession",
            deferrable=True,
            initially="DEFERRED",
        ),
        # Foreign key constraint for project accession
        ForeignKeyConstraint(
            ["project_accession", "authority"],
            ["accession_registry.accession", "accession_registry.authority"],
            name="fk_proj_acc",
        ),
        # Foreign key constraint for sample accession
        ForeignKeyConstraint(
            ["sample_accession", "authority"],
            ["accession_registry.accession", "accession_registry.authority"],
            name="fk_samp_acc",
        ),
        # This is a simplified version of the SQL constraint:
        # UNIQUE (experiment_id, authority) WHERE (status = 'accepted' AND accession IS NOT NULL)
        # SQLAlchemy doesn't directly support WHERE clauses in constraints, so this would need custom SQL
    )


# ExperimentFetched table is no longer in the schema.sql, so we're removing this model

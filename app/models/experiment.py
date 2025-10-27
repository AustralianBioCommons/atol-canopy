import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, ForeignKeyConstraint, String, Text, Enum as SQLAlchemyEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship, backref

from app.db.session import Base


class Experiment(Base):
    """
    Experiment model for storing experiment information.
    
    This model corresponds to the 'experiment' table in the database.
    """
    __tablename__ = "experiment"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sample_id = Column(UUID(as_uuid=True), ForeignKey("sample.id", ondelete="CASCADE"), nullable=False)
    bpa_package_id = Column(Text, unique=True, nullable=False)
    bpa_json = Column(JSONB, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    # Relationships
    sample = relationship("Sample", backref=backref("exp_sample_records", cascade="all, delete-orphan"))


class ExperimentSubmission(Base):
    """
    ExperimentSubmission model for storing experiment data staged for submission to ENA.
    
    This model corresponds to the 'experiment_submission' table in the database.
    """
    __tablename__ = "experiment_submission"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    experiment_id = Column(UUID(as_uuid=True), ForeignKey("experiment.id", ondelete="CASCADE"), nullable=True)
    authority = Column(SQLAlchemyEnum("ENA", "NCBI", "DDBJ", name="authority_type"), nullable=False, default="ENA")
    status = Column(SQLAlchemyEnum("draft", "ready", "submitted", "accepted", "rejected", "replaced", name="submission_status"), nullable=False, default="draft")
    
    sample_id = Column(UUID(as_uuid=True), ForeignKey("sample.id", ondelete="SET NULL"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("project.id", ondelete="SET NULL"), nullable=True)
    
    project_accession = Column(Text, nullable=True)
    sample_accession = Column(Text, nullable=True)
    
    prepared_payload = Column(JSONB, nullable=True)
    response_payload = Column(JSONB, nullable=True)
    accession = Column(Text, nullable=True)
    
    # Constant to help the composite FK
    entity_type_const = Column(Text, nullable=False, default="experiment", server_default="experiment")
    submitted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    # Relationships
    experiment = relationship("Experiment", backref=backref("exp_submission_records", cascade="all, delete-orphan"))
    sample = relationship("Sample", backref=backref("exp_sample_submission_records", cascade="all, delete-orphan"))
    project = relationship("Project", backref=backref("exp_project_submission_records", cascade="all, delete-orphan"))
    
    # Table constraints
    __table_args__ = (
        # Foreign key constraint for accession registry (self)
        ForeignKeyConstraint(
            ['accession', 'authority', 'entity_type_const', 'experiment_id'],
            ['accession_registry.accession', 'accession_registry.authority', 'accession_registry.entity_type', 'accession_registry.entity_id'],
            name='fk_self_accession',
            deferrable=True,
            initially='DEFERRED'
        ),
        # Foreign key constraint for project accession
        ForeignKeyConstraint(
            ['project_accession', 'authority'],
            ['accession_registry.accession', 'accession_registry.authority'],
            name='fk_proj_acc'
        ),
        # Foreign key constraint for sample accession
        ForeignKeyConstraint(
            ['sample_accession', 'authority'],
            ['accession_registry.accession', 'accession_registry.authority'],
            name='fk_samp_acc'
        ),
        # This is a simplified version of the SQL constraint:
        # UNIQUE (experiment_id, authority) WHERE (status = 'accepted' AND accession IS NOT NULL)
        # SQLAlchemy doesn't directly support WHERE clauses in constraints, so this would need custom SQL
    )


# ExperimentFetched table is no longer in the schema.sql, so we're removing this model

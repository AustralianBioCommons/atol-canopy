import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, ForeignKeyConstraint, Text, BigInteger, String, Enum as SQLAlchemyEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db.session import Base


class Read(Base):
    """
    Read model for storing data about sequencing reads linked to experiments.
    
    This model corresponds to the 'read' table in the database.
    """
    __tablename__ = "read"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    experiment_id = Column(UUID(as_uuid=True), ForeignKey("experiment.id"), nullable=False)
    bpa_resource_id = Column(Text, unique=True, nullable=False)
    bpa_json = Column(JSONB, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    # Relationships
    experiment = relationship("Experiment", backref="reads")


class ReadSubmission(Base):
    """
    ReadSubmission model for storing read data staged for submission to ENA.
    
    This model corresponds to the 'read_submission' table in the database.
    """
    __tablename__ = "read_submission"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    read_id = Column(UUID(as_uuid=True), ForeignKey("read.id"), nullable=False)
    authority = Column(SQLAlchemyEnum("ENA", "NCBI", "DDBJ", name="authority_type"), nullable=False, default="ENA")
    status = Column(SQLAlchemyEnum("draft", "ready", "submitted", "accepted", "rejected", "replaced", name="submission_status"), nullable=False, default="draft")
    
    prepared_payload = Column(JSONB, nullable=False)
    response_payload = Column(JSONB, nullable=True)
    
    experiment_id = Column(UUID(as_uuid=True), ForeignKey("experiment.id"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("project.id"), nullable=False)
    
    experiment_accession = Column(Text, nullable=True)
    
    accession = Column(Text, nullable=True)
    
    # Constant to help the composite FK
    entity_type_const = Column(Text, nullable=False, default="read", server_default="read")
    
    created_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    # Relationships
    read = relationship("Read", backref="submission_records")
    experiment = relationship("Experiment")
    project = relationship("Project")
    
    # Table constraints
    __table_args__ = (
        # Foreign key constraint for accession registry (self)
        ForeignKeyConstraint(
            ['accession', 'authority', 'entity_type_const', 'read_id'],
            ['accession_registry.accession', 'accession_registry.authority', 'accession_registry.entity_type', 'accession_registry.entity_id'],
            name='fk_self_accession',
            deferrable=True,
            initially='DEFERRED'
        ),
        # Foreign key constraint for experiment accession
        ForeignKeyConstraint(
            ['experiment_accession', 'authority'],
            ['accession_registry.accession', 'accession_registry.authority'],
            name='fk_exp_acc'
        ),
        # This is a simplified version of the SQL constraint:
        # UNIQUE (read_id, authority) WHERE (status = 'accepted' AND accession IS NOT NULL)
        # SQLAlchemy doesn't directly support WHERE clauses in constraints, so this would need custom SQL
    )

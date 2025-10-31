import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, ForeignKeyConstraint, String, Text, Enum as SQLAlchemyEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship, backref

from app.db.session import Base


class Sample(Base):
    """
    Sample model for storing biological sample information.
    
    This model corresponds to the 'sample' table in the database.
    """
    __tablename__ = "sample"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organism_key = Column("organism_key", ForeignKey("organism.grouping_key", ondelete="CASCADE"), nullable=False)
    bpa_sample_id = Column(Text, unique=True, nullable=False)
    bpa_json = Column(JSONB, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    # Relationships
    organism = relationship("Organism", backref=backref("samples", cascade="all, delete-orphan"))


class SampleSubmission(Base):
    """
    SampleSubmission model for storing sample data staged for submission to ENA.
    
    This model corresponds to the 'sample_submission' table in the database.
    """
    __tablename__ = "sample_submission"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sample_id = Column(UUID(as_uuid=True), ForeignKey("sample.id", ondelete="CASCADE"), nullable=True)
    authority = Column(SQLAlchemyEnum("ENA", "NCBI", "DDBJ", name="authority_type"), nullable=False, default="ENA")
    status = Column(SQLAlchemyEnum("draft", "ready", "submitting", "accepted", "rejected", "replaced", name="submission_status"), nullable=False, default="draft")
    prepared_payload = Column(JSONB, nullable=False)
    response_payload = Column(JSONB, nullable=True)
    accession = Column(Text, nullable=True)
    biosample_accession = Column(Text, nullable=True)
    entity_type_const = Column(Text, nullable=False, default="sample", server_default="sample")
    submitted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    # Broker lease/claim fields
    batch_id = Column(UUID(as_uuid=True), nullable=True)
    lock_acquired_at = Column(DateTime, nullable=True)
    lock_expires_at = Column(DateTime, nullable=True)
    
    # Relationships
    sample = relationship("Sample", backref=backref("sample_submission_records", cascade="all, delete-orphan"))
    
    # Table constraints
    __table_args__ = (
        # Foreign key constraint for accession registry
        ForeignKeyConstraint(
            ['accession', 'authority', 'entity_type_const', 'sample_id'],
            ['accession_registry.accession', 'accession_registry.authority', 'accession_registry.entity_type', 'accession_registry.entity_id'],
            name='fk_self_accession',
            deferrable=True,
            initially='DEFERRED'
        ),
        # This is a simplified version of the SQL constraint:
        # UNIQUE (sample_id, authority) WHERE (status = 'accepted' AND accession IS NOT NULL)
        # SQLAlchemy doesn't directly support WHERE clauses in constraints, so this would need custom SQL
    )


# SampleFetched table is no longer in the schema.sql, so we're removing this model


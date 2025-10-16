import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, Enum as SQLAlchemyEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.session import Base


class Sample(Base):
    """
    Sample model for storing biological sample information.
    
    This model corresponds to the 'sample' table in the database.
    """
    __tablename__ = "sample"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organism_grouping_key = Column("organism_grouping_key", ForeignKey("organism.grouping_key"), nullable=False)
    bpa_sample_id = Column(String(255), unique=True, nullable=False)
    bpa_json = Column(JSONB, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    # Relationships
    organism = relationship("Organism", backref="samples")


class SampleSubmission(Base):
    """
    SampleSubmission model for storing sample data staged for submission to ENA.
    
    This model corresponds to the 'sample_submission' table in the database.
    """
    __tablename__ = "sample_submission"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sample_id = Column(UUID(as_uuid=True), ForeignKey("sample.id"), nullable=True)
    authority = Column(SQLAlchemyEnum("ENA", "NCBI", "DDBJ", name="authority_type"), nullable=False, default="ENA")
    status = Column(SQLAlchemyEnum("draft", "ready", "submitted", "accepted", "rejected", "replaced", name="submission_status"), nullable=False, default="draft")
    prepared_payload = Column(JSONB, nullable=False)
    response_payload = Column(JSONB, nullable=True)
    accession = Column(String(255), nullable=True)
    biosample_accession = Column(String(255), nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    # Relationships
    sample = relationship("Sample", backref="submission_records")
    
    # Table constraints
    __table_args__ = (
        # This is a simplified version of the SQL constraint:
        # UNIQUE (sample_id, authority) WHERE (status = 'accepted' AND accession IS NOT NULL)
        # SQLAlchemy doesn't directly support WHERE clauses in constraints, so this would need custom SQL
    )


# SampleFetched table is no longer in the schema.sql, so we're removing this model


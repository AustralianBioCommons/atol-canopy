import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, ForeignKeyConstraint, String, Text, Float, Enum as SQLAlchemyEnum, text
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
    specimen_id = Column(Text, nullable=True)
    specimen_id_description = Column(Text, nullable=True)
    identified_by = Column(Text, nullable=True)
    specimen_custodian = Column(Text, nullable=True)
    sample_custodian = Column(Text, nullable=True)
    lifestage = Column(Text, nullable=False)
    sex = Column(Text, nullable=False)
    organism_part = Column(Text, nullable=False)
    region_and_locality = Column(Text, nullable=False)
    state_or_region = Column(Text, nullable=True)
    country_or_sea = Column(Text, nullable=False)
    indigenous_location = Column(Text, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    elevation = Column(Float, nullable=True)
    depth = Column(Float, nullable=True)
    habitat = Column(Text, nullable=False)
    collection_method = Column(Text, nullable=True)
    collection_date = Column(Text, nullable=True)
    collected_by = Column(Text, nullable=False, server_default=text("'not provided'"))
    collecting_institution = Column(Text, nullable=False, server_default=text("'not provided'"))
    collection_permit = Column(Text, nullable=True)
    data_context = Column(Text, nullable=True)
    bioplatforms_project_id = Column(Text, nullable=True)
    title = Column(Text, nullable=True)
    sample_same_as = Column(Text, nullable=True)
    sample_derived_from = Column(Text, nullable=True)
    specimen_voucher = Column(Text, nullable=True)
    tolid = Column(Text, nullable=True)
    preservation_method = Column(Text, nullable=True)
    preservation_temperature = Column(Text, nullable=True)
    project_name = Column(Text, nullable=True)
    biosample_accession = Column(Text, nullable=True)
    # bpa_json = Column(JSONB, nullable=False)
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
    attempt_id = Column(UUID(as_uuid=True), nullable=True)
    
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


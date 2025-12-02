import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, Float, BigInteger, Enum as SQLAlchemyEnum, PrimaryKeyConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship, backref

from app.db.session import Base


class Assembly(Base):
    """
    Assembly model for storing genomic assembly information.
    
    This model corresponds to the 'assembly' table in the database.
    """
    __tablename__ = "assembly"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organism_key = Column("organism_key", ForeignKey("organism.grouping_key"), nullable=False)
    sample_id = Column(UUID(as_uuid=True), ForeignKey("sample.id"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("project.id"), nullable=True)
    
    # Assembly metadata fields
    assembly_name = Column(Text, nullable=False)
    assembly_type = Column(Text, nullable=False, default="clone or isolate")
    coverage = Column(Float, nullable=False)
    program = Column(String(255), nullable=False)
    mingaplength = Column(Float, nullable=True)
    moleculetype = Column(SQLAlchemyEnum("genomic DNA", "genomic RNA", name="molecule_type"), nullable=False, default="genomic DNA")
    fasta = Column(String(255), nullable=False)
    version = Column(String(255), nullable=False)
    
    created_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    # Relationships
    organism = relationship("Organism", backref="assemblies")
    sample = relationship("Sample", backref="assemblies")
    project = relationship("Project", backref="assemblies")


class AssemblySubmission(Base):
    """
    AssemblySubmission model for storing assembly data staged for submission to ENA.
    
    This model corresponds to the 'assembly_submission' table in the database.
    """
    __tablename__ = "assembly_submission"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assembly_id = Column(UUID(as_uuid=True), ForeignKey("assembly.id", ondelete="CASCADE"), nullable=False)
    assembly_name = Column(Text, nullable=False)
    authority = Column(SQLAlchemyEnum("ENA", "NCBI", "DDBJ", name="authority_type"), nullable=False, default="ENA")
    accession = Column(Text, nullable=True)
    organism_key = Column(Text, ForeignKey("organism.grouping_key", ondelete="CASCADE"), nullable=False)
    sample_id = Column(UUID(as_uuid=True), ForeignKey("sample.id", ondelete="SET NULL"), nullable=True)
    
    internal_json = Column(JSONB, nullable=True)
    prepared_payload = Column(JSONB, nullable=True)
    returned_payload = Column(JSONB, nullable=True)
    
    status = Column(SQLAlchemyEnum("draft", "ready", "submitting", "accepted", "rejected", "replaced", name="submission_status"), nullable=False, default="draft")
    submitted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    # Relationships
    assembly = relationship("Assembly", backref=backref("assembly_submission_records", cascade="all, delete-orphan"))
    organism = relationship("Organism", backref=backref("assemblies_organism", cascade="all, delete-orphan"))
    sample = relationship("Sample", backref="assemblies_sample")


class AssemblyOutputFile(Base):
    """
    AssemblyOutputFile model for storing output files from assembly pipelines.
    
    This model corresponds to the 'assembly_output_file' table in the database.
    """
    __tablename__ = "assembly_output_file"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assembly_id = Column(UUID(as_uuid=True), ForeignKey("assembly.id"), nullable=True)
    type = Column(SQLAlchemyEnum("QC", "Other", name="assembly_output_file_type"), nullable=False)
    file_name = Column(Text, nullable=False)
    file_location = Column(Text, nullable=False)
    file_size = Column(BigInteger, nullable=True)
    file_checksum = Column(Text, nullable=True)
    file_format = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    # Relationships
    assembly = relationship("Assembly", backref=backref("output_files", cascade="all, delete-orphan"))


class AssemblyRead(Base):
    """
    AssemblyRead model for storing the many-to-many relationship between assemblies and reads.
    
    This model corresponds to the 'assembly_read' table in the database.
    """
    __tablename__ = "assembly_read"
    
    assembly_id = Column(UUID(as_uuid=True), ForeignKey("assembly.id"), nullable=False)
    read_id = Column(UUID(as_uuid=True), ForeignKey("read.id"), nullable=False)
    
    # Define composite primary key
    __table_args__ = (
        # SQLAlchemy syntax for composite primary key
        # This matches the SQL: PRIMARY KEY (assembly_id, read_id)
        PrimaryKeyConstraint('assembly_id', 'read_id'),
    )
    
    # Relationships
    assembly = relationship("Assembly", backref=backref("assembly_reads", cascade="all, delete-orphan"))
    read = relationship("Read", backref=backref("reads_assembly", cascade="all, delete-orphan"))

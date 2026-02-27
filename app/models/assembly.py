import uuid

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    PrimaryKeyConstraint,
    Text,
    func,
)
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import backref, relationship

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
    tol_id = Column(Text, nullable=True)
    data_types = Column(
        SQLAlchemyEnum(
            "PACBIO_SMRT",
            "PACBIO_SMRT_HIC",
            "OXFORD_NANOPORE",
            "OXFORD_NANOPORE_HIC",
            "PACBIO_SMRT_OXFORD_NANOPORE",
            "PACBIO_SMRT_OXFORD_NANOPORE_HIC",
            name="assembly_data_types",
        ),
        nullable=False,
    )
    coverage = Column(Float, nullable=False)
    program = Column(Text, nullable=False)
    mingaplength = Column(Float, nullable=True)
    moleculetype = Column(
        SQLAlchemyEnum("genomic DNA", "genomic RNA", name="molecule_type"),
        nullable=False,
        default="genomic DNA",
    )
    description = Column(Text, nullable=True)
    version = Column(Integer, nullable=False, default=1)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    organism = relationship("Organism", backref="assemblies")
    sample = relationship("Sample", backref="assemblies")
    project = relationship("Project", backref="assemblies")


class AssemblyRun(Base):
    """
    AssemblyRun model for reserving versions and tracking assembly intents.

    This model corresponds to the 'assembly_run' table in the database.
    """

    __tablename__ = "assembly_run"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organism_key = Column("organism_key", ForeignKey("organism.grouping_key"), nullable=False)
    sample_id = Column(UUID(as_uuid=True), ForeignKey("sample.id"), nullable=False)
    data_types = Column(
        SQLAlchemyEnum(
            "PACBIO_SMRT",
            "PACBIO_SMRT_HIC",
            "OXFORD_NANOPORE",
            "OXFORD_NANOPORE_HIC",
            "PACBIO_SMRT_OXFORD_NANOPORE",
            "PACBIO_SMRT_OXFORD_NANOPORE_HIC",
            name="assembly_data_types",
        ),
        nullable=False,
    )
    version = Column(Integer, nullable=False)
    tol_id = Column(Text, nullable=True)
    status = Column(Text, nullable=False, default="reserved")

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    organism = relationship("Organism", backref="assembly_runs")
    sample = relationship("Sample", backref="assembly_runs")


class AssemblySubmission(Base):
    """
    AssemblySubmission model for storing assembly submission data to ENA.
    Simplified workflow without broker integration.

    This model corresponds to the 'assembly_submission' table in the database.
    """

    __tablename__ = "assembly_submission"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assembly_id = Column(
        UUID(as_uuid=True), ForeignKey("assembly.id", ondelete="CASCADE"), nullable=False
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

    # ENA accessions
    accession = Column(Text, nullable=True)
    sample_accession = Column(Text, nullable=True)
    project_accession = Column(Text, nullable=True)

    # Submission payloads
    manifest_json = Column(JSONB, nullable=True)
    submission_xml = Column(Text, nullable=True)
    response_payload = Column(JSONB, nullable=True)

    # Metadata
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    submitted_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    assembly = relationship(
        "Assembly", backref=backref("submissions", cascade="all, delete-orphan")
    )
    user = relationship("User", backref="assembly_submissions")


class AssemblyFile(Base):
    """
    AssemblyFile model for storing files associated with assemblies.
    Includes FASTA, AGP, QC reports, statistics, and other file types.

    This model corresponds to the 'assembly_file' table in the database.
    """

    __tablename__ = "assembly_file"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assembly_id = Column(
        UUID(as_uuid=True), ForeignKey("assembly.id", ondelete="CASCADE"), nullable=False
    )
    file_type = Column(
        SQLAlchemyEnum(
            "FASTA",
            "QC_REPORT",
            "STATISTICS",
            "OTHER",
            name="assembly_file_type",
        ),
        nullable=False,
    )
    file_name = Column(Text, nullable=False)
    file_location = Column(Text, nullable=False)
    file_size = Column(BigInteger, nullable=True)
    file_checksum = Column(Text, nullable=True)
    file_checksum_method = Column(Text, nullable=True, default="MD5")
    file_format = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    assembly = relationship("Assembly", backref=backref("files", cascade="all, delete-orphan"))


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
        PrimaryKeyConstraint("assembly_id", "read_id"),
    )

    # Relationships
    assembly = relationship(
        "Assembly", backref=backref("assembly_reads", cascade="all, delete-orphan")
    )
    read = relationship("Read", backref=backref("reads_assembly", cascade="all, delete-orphan"))

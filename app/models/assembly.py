import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    PrimaryKeyConstraint,
    Text,
    UniqueConstraint,
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
    taxon_id = Column("taxon_id", ForeignKey("organism.taxon_id"), nullable=False)
    sample_id = Column(UUID(as_uuid=True), ForeignKey("sample.id"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("project.id"), nullable=True)

    # Assembly metadata fields
    assembly_name = Column(Text, nullable=True)
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
    coverage = Column(Float, nullable=True)
    program = Column(Text, nullable=True)
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

    long_read_specimen_sample_id = Column(
        UUID(as_uuid=True), ForeignKey("sample.id"), nullable=True
    )
    hic_specimen_sample_id = Column(UUID(as_uuid=True), ForeignKey("sample.id"), nullable=True)
    hic_specimen_sample_ids = Column(JSONB, nullable=True)
    manifest_json = Column(JSONB, nullable=True)

    # Relationships
    organism = relationship("Organism", backref="assemblies")
    sample = relationship("Sample", foreign_keys=[sample_id], backref="assemblies")
    long_read_specimen_sample = relationship("Sample", foreign_keys=[long_read_specimen_sample_id])
    hic_specimen_sample = relationship("Sample", foreign_keys=[hic_specimen_sample_id])
    project = relationship("Project", backref="assemblies")


class AssemblyRun(Base):
    """
    A single pipeline invocation for an assembly, identified by a GitHub repo + commit.

    Each AssemblyRun represents one end-to-end execution of the assembly pipeline.
    All stages within that run share the same github_repo and git_commit.
    """

    __tablename__ = "assembly_run"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assembly_id = Column(
        UUID(as_uuid=True), ForeignKey("assembly.id", ondelete="CASCADE"), nullable=False
    )
    github_repo = Column(Text, nullable=False)
    git_commit = Column(Text, nullable=False)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "assembly_id",
            "github_repo",
            "git_commit",
            name="uq_assembly_run_assembly_repo_commit",
        ),
    )

    assembly = relationship("Assembly", backref=backref("runs", cascade="all, delete-orphan"))


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


class AssemblyStage(Base):
    """Catalog of known assembly pipeline/manual stages."""

    __tablename__ = "assembly_stage"

    name = Column(Text, primary_key=True)
    category = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)


class AssemblyStageRun(Base):
    """A single reported run of an assembly stage (pipeline or manual)."""

    __tablename__ = "assembly_stage_run"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assembly_run_id = Column(
        UUID(as_uuid=True), ForeignKey("assembly_run.id", ondelete="CASCADE"), nullable=False
    )
    stage_name = Column(Text, ForeignKey("assembly_stage.name"), nullable=False)
    status = Column(Text, nullable=False)
    external_run_id = Column(Text, nullable=True)
    stats = Column(JSONB, nullable=False, default=dict)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("assembly_run_id", "stage_name", name="uq_stage_run_assembly_run_stage"),
    )

    assembly_run = relationship(
        "AssemblyRun", backref=backref("stage_runs", cascade="all, delete-orphan")
    )
    stage = relationship("AssemblyStage", backref="runs")


class AssemblyStageRunFile(Base):
    """Files attached to an assembly stage run."""

    __tablename__ = "assembly_stage_run_file"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assembly_stage_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("assembly_stage_run.id", ondelete="CASCADE"),
        nullable=False,
    )
    storage_type = Column(Text, nullable=False)
    endpoint = Column(Text, nullable=True)
    location_root = Column(Text, nullable=False)
    location_path = Column(Text, nullable=False)
    sha256sum = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    stage_run = relationship(
        "AssemblyStageRun", backref=backref("files", cascade="all, delete-orphan")
    )

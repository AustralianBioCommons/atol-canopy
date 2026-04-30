import uuid

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Text,
    func,
)
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import backref, relationship

from app.db.session import Base


class QcRead(Base):
    """Aggregate QC metrics for one QC output set linked to an experiment."""

    __tablename__ = "qc_read"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    experiment_id = Column(
        UUID(as_uuid=True), ForeignKey("experiment.id", ondelete="CASCADE"), nullable=False
    )
    base_count = Column(BigInteger, nullable=False)
    read_count = Column(BigInteger, nullable=False)
    qc_bases_removed = Column(BigInteger, nullable=False)
    qc_reads_removed = Column(BigInteger, nullable=False)
    mean_gc_content = Column(Float, nullable=False)
    n50_length = Column(BigInteger, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    experiment = relationship(
        "Experiment", backref=backref("qc_reads", cascade="all, delete-orphan")
    )
    files = relationship("QcReadFile", back_populates="qc_read", cascade="all, delete-orphan")
    submission_records = relationship(
        "QcReadSubmission", back_populates="qc_read", cascade="all, delete-orphan"
    )


class QcReadFile(Base):
    """One physical file belonging to a QcRead output set (CRAM, FASTQ R1, or FASTQ R2)."""

    __tablename__ = "qc_read_file"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    qc_read_id = Column(
        UUID(as_uuid=True), ForeignKey("qc_read.id", ondelete="CASCADE"), nullable=False
    )
    # 'cram', 'fastq_r1', or 'fastq_r2'
    file_type = Column(Text, nullable=False)
    storage_backend = Column(Text, nullable=False)
    storage_profile = Column(Text, nullable=False)
    bucket_name = Column(Text, nullable=False)
    path_to_file = Column(Text, nullable=False)
    md5_checksum = Column(Text, nullable=False)
    sha256_checksum = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    qc_read = relationship("QcRead", back_populates="files")

    __table_args__ = (
        CheckConstraint(
            "file_type IN ('cram', 'fastq_r1', 'fastq_r2')", name="ck_qc_read_file_type"
        ),
        CheckConstraint("md5_checksum ~ '^[a-f0-9]{32}$'", name="ck_qc_read_file_md5"),
        CheckConstraint("sha256_checksum ~ '^[a-f0-9]{64}$'", name="ck_qc_read_file_sha256"),
    )


class QcReadSubmission(Base):
    """ENA submission record for a QcRead. Mirrors the lifecycle of ReadSubmission."""

    __tablename__ = "qc_read_submission"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    qc_read_id = Column(
        UUID(as_uuid=True), ForeignKey("qc_read.id", ondelete="CASCADE"), nullable=False
    )
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
    prepared_payload = Column(JSONB, nullable=False)
    response_payload = Column(JSONB, nullable=True)
    accession = Column(Text, nullable=True)
    entity_type_const = Column(Text, nullable=False, default="qc_read", server_default="qc_read")

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

    qc_read = relationship("QcRead", back_populates="submission_records")
    experiment = relationship(
        "Experiment",
        backref=backref("qc_read_submission_records", cascade="all, delete-orphan"),
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["accession", "authority", "entity_type_const", "qc_read_id"],
            [
                "accession_registry.accession",
                "accession_registry.authority",
                "accession_registry.entity_type",
                "accession_registry.entity_id",
            ],
            name="fk_qc_read_submission_accession",
            deferrable=True,
            initially="DEFERRED",
        ),
    )

import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Text,
)
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import backref, relationship

from app.db.session import Base


class Read(Base):
    """
    Read model for storing data about sequencing reads linked to experiments.

    This model corresponds to the 'read' table in the database.
    """

    __tablename__ = "read"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    experiment_id = Column(
        UUID(as_uuid=True), ForeignKey("experiment.id", ondelete="CASCADE"), nullable=True
    )
    bpa_resource_id = Column(Text, unique=True, nullable=False)
    bpa_dataset_id = Column(Text, nullable=True)
    file_name = Column(Text, nullable=True)
    file_checksum = Column(Text, nullable=True)
    file_format = Column(Text, nullable=True)
    optional_file = Column(Boolean, nullable=False, default=True)
    bioplatforms_url = Column(Text, nullable=True)
    read_number = Column(Text, nullable=True)
    lane_number = Column(Text, nullable=True)
    # bpa_json = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    experiment = relationship("Experiment", backref=backref("reads", cascade="all, delete-orphan"))


"""
file_name = Column(Text, nullable=False)
    file_checksum = Column(Text, nullable=False)
    file_format = Column(Text, nullable=False)
    file_submission_date = Column(Text, nullable=True)
    optional_file = Column(Text, nullable=True)
    bioplatforms_url = Column(Text, nullable=True)
    reads_access_date = Column(Text, nullable=True)
    read_number = Column(Text, nullable=True)
    lane_number = Column(Text, nullable=True)
    sra_run_accession = Column(Text, nullable=True)
    run_read_count = Column(Text, nullable=True)
    run_base_count = Column(Text, nullable=True)
"""


class ReadSubmission(Base):
    """
    ReadSubmission model for storing read data staged for submission to ENA.

    This model corresponds to the 'read_submission' table in the database.
    """

    __tablename__ = "read_submission"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    read_id = Column(UUID(as_uuid=True), ForeignKey("read.id", ondelete="CASCADE"), nullable=False)
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

    # TODO determine whether these relations are needed based on query requirements
    experiment_id = Column(
        UUID(as_uuid=True), ForeignKey("experiment.id", ondelete="CASCADE"), nullable=True
    )
    project_id = Column(
        UUID(as_uuid=True), ForeignKey("project.id", ondelete="SET NULL"), nullable=True
    )

    experiment_accession = Column(Text, nullable=True)

    accession = Column(Text, nullable=True)

    # Constant to help the composite FK
    entity_type_const = Column(Text, nullable=False, default="read", server_default="read")

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    read = relationship(
        "Read", backref=backref("read_submission_records", cascade="all, delete-orphan")
    )
    experiment = relationship(
        "Experiment", backref=backref("read_exp_submission_records", cascade="all, delete-orphan")
    )
    project = relationship(
        "Project", backref=backref("read_proj_submission_records", cascade="all, delete-orphan")
    )

    # Broker lease/claim fields
    attempt_id = Column(UUID(as_uuid=True), nullable=True)
    finalised_attempt_id = Column(UUID(as_uuid=True), nullable=True)
    lock_acquired_at = Column(DateTime(timezone=True), nullable=True)
    lock_expires_at = Column(DateTime(timezone=True), nullable=True)

    # Table constraints
    __table_args__ = (
        # Foreign key constraint for accession registry (self)
        ForeignKeyConstraint(
            ["accession", "authority", "entity_type_const", "read_id"],
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
        # Foreign key constraint for experiment accession
        ForeignKeyConstraint(
            ["experiment_accession", "authority"],
            ["accession_registry.accession", "accession_registry.authority"],
            name="fk_exp_acc",
        ),
        # This is a simplified version of the SQL constraint:
        # UNIQUE (read_id, authority) WHERE (status = 'accepted' AND accession IS NOT NULL)
        # SQLAlchemy doesn't directly support WHERE clauses in constraints, so this would need custom SQL
    )

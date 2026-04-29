import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
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

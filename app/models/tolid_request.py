import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, Text, func
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import backref, relationship

from app.db.session import Base


class TolidRequest(Base):
    """Durable ToLID request state for a specimen sample."""

    __tablename__ = "tolid_request"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sample_id = Column(UUID(as_uuid=True), ForeignKey("sample.id", ondelete="CASCADE"), nullable=False)
    tolid_external_id = Column(Text, nullable=False)
    taxon_id = Column(
        Integer, ForeignKey("organism.taxon_id", ondelete="CASCADE"), nullable=False
    )
    scientific_name = Column(Text, nullable=True)
    tolid = Column(Text, nullable=True)
    request_id = Column(Text, nullable=True)
    status = Column(
        SQLAlchemyEnum(
            "not_requested",
            "pending",
            "assigned",
            "failed",
            name="tolid_request_status",
        ),
        nullable=False,
        default="not_requested",
    )
    last_requested_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    sample = relationship(
        "Sample",
        backref=backref("tolid_request_record", uselist=False, cascade="all, delete-orphan"),
    )
    organism = relationship(
        "Organism",
        backref=backref("tolid_request_records", cascade="all, delete-orphan"),
    )

    __table_args__ = (
        Index("uq_tolid_request_sample_id", "sample_id", unique=True),
        Index("idx_tolid_request_status", "status"),
        Index("idx_tolid_request_status_last_requested_at", "status", "last_requested_at"),
        Index("idx_tolid_request_request_id", "request_id"),
    )

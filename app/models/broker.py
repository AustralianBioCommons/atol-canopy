import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.session import Base


class SubmissionAttempt(Base):
    __tablename__ = "submission_attempt"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organism_key = Column(
        Text, ForeignKey("organism.grouping_key", ondelete="RESTRICT"), nullable=True
    )
    campaign_label = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="processing")
    lock_acquired_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    lock_expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class SubmissionEvent(Base):
    __tablename__ = "submission_event"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id = Column(
        UUID(as_uuid=True), ForeignKey("submission_attempt.id", ondelete="CASCADE"), nullable=False
    )
    entity_type = Column(String, nullable=False)  # expects values: sample|experiment|read
    submission_id = Column(UUID(as_uuid=True), nullable=False)
    action = Column(String, nullable=False)  # claimed|accepted|rejected|released|expired|progress
    accession = Column(Text, nullable=True)
    details = Column(JSONB, nullable=True)
    at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

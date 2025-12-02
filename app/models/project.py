import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, Enum as SQLAlchemyEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db.session import Base


class Project(Base):
    """
    Project model for storing project information linked to experiments.
    
    This model corresponds to the 'project' table in the database.
    """
    __tablename__ = "project"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organism_key = Column("organism_key", ForeignKey("organism.grouping_key", ondelete="CASCADE"), nullable=False)
    project_type = Column(SQLAlchemyEnum("root", "genomic_data", "assembly", name="project_type"), nullable=False)
    project_accession = Column(Text, unique=True, nullable=True)
    study_type = Column(Text, nullable=False)
    alias = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=False)
    centre_name = Column(Text, nullable=True, default="AToL")
    study_attributes = Column(JSONB, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    status = Column(SQLAlchemyEnum("draft", "ready", "submitting", "rejected", "accepted", "replaced", name="submission_status"), nullable=False, default="draft")
    authority = Column(SQLAlchemyEnum("ENA", "NCBI", "DDBJ", name="authority_type"), nullable=False, default="ENA")
    created_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

class ProjectSubmission(Base):
    __tablename__ = "project_submission"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    authority = Column(SQLAlchemyEnum("ENA", "NCBI", "DDBJ", name="authority_type"), nullable=False, default="ENA")
    status = Column(SQLAlchemyEnum("draft", "ready", "submitting", "rejected", "accepted", "replaced", name="submission_status"), nullable=False, default="draft")

    prepared_payload = Column(JSONB, nullable=True)
    response_payload = Column(JSONB, nullable=True)

    accession = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    # attempt linkage
    attempt_id = Column(UUID(as_uuid=True), nullable=True)
    finalised_attempt_id = Column(UUID(as_uuid=True), nullable=True)

    # broker lease/claim fields
    lock_acquired_at = Column(DateTime, nullable=True)
    lock_expires_at = Column(DateTime, nullable=True)

"""
class ProjectExperiment(Base):
    #ProjectExperiment model for linking projects to experiments.
    
    #This model corresponds to the 'project_experiment' table in the database.
    __tablename__ = "project_experiment"
    
    # Composite primary key fields
    project_id = Column(UUID(as_uuid=True), ForeignKey("project.id"), nullable=False, primary_key=True)
    experiment_id = Column(UUID(as_uuid=True), ForeignKey("experiment.id"), nullable=False, primary_key=True)
    
    # Relationships
    project = relationship("Project", backref="project_experiments")
    experiment = relationship("Experiment", backref="project_experiments")
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, Enum as SQLAlchemyEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db.session import Base


class Bioproject(Base):
    """
    Bioproject model for storing project information linked to experiments.
    
    This model corresponds to the 'bioproject' table in the database.
    """
    __tablename__ = "bioproject"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_type = Column(SQLAlchemyEnum("organism", "genomic_data", "assembly", name="bioproject_type"), nullable=False)
    bioproject_accession = Column(Text, unique=True, nullable=True)
    study_type = Column(Text, nullable=False)
    alias = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=False)
    centre_name = Column(Text, nullable=True)
    study_attributes = Column(JSONB, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    status = Column(SQLAlchemyEnum("draft", "ready", "submitted", "accepted", "rejected", "replaced", name="submission_status"), nullable=False, default="draft")
    authority = Column(SQLAlchemyEnum("ENA", "NCBI", "DDBJ", name="authority_type"), nullable=False, default="ENA")
    created_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))


class BioprojectExperiment(Base):
    """
    BioprojectExperiment model for linking bioprojects to experiments.
    
    This model corresponds to the 'bioproject_experiment' table in the database.
    """
    __tablename__ = "bioproject_experiment"
    
    # Composite primary key fields
    bioproject_id = Column(UUID(as_uuid=True), ForeignKey("bioproject.id"), nullable=False, primary_key=True)
    experiment_id = Column(UUID(as_uuid=True), ForeignKey("experiment.id"), nullable=False, primary_key=True)
    
    # Relationships
    bioproject = relationship("Bioproject", backref="bioproject_experiments")
    experiment = relationship("Experiment", backref="bioproject_experiments")

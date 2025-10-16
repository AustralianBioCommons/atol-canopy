import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db.session import Base


class BPAInitiative(Base):
    """
    BPA Initiative model for storing information about BPA initiatives.
    
    This model corresponds to the 'bpa_initiative' table in the database.
    """
    __tablename__ = "bpa_initiative"
    
    project_code = Column(String(255), primary_key=True)
    title = Column(Text, nullable=False)
    url = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

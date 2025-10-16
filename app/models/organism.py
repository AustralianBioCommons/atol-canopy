import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, Text, String
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.session import Base


class Organism(Base):
    """
    Organism model for storing taxonomic information.
    
    This model corresponds to the 'organism' table in the database.
    """
    __tablename__ = "organism"
    
    # In the new schema, grouping_key is the primary key
    grouping_key = Column(Text, primary_key=True)
    tax_id = Column(Integer, unique=True, nullable=False)
    scientific_name = Column(Text, nullable=True)
    common_name = Column(Text, nullable=True)
    common_name_source = Column(Text, nullable=True)
    bpa_json = Column(JSONB, nullable=True)
    taxonomy_lineage_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

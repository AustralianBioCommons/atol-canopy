import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text
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
    genus = Column(Text, nullable=True)
    species = Column(Text, nullable=True)
    infraspecific_epithet = Column(Text, nullable=True)
    culture_or_strain_id = Column(Text, nullable=True)
    authority = Column(Text, nullable=True)
    atol_scientific_name = Column(Text, nullable=True)
    tax_string = Column(Text, nullable=True)
    ncbi_order = Column(Text, nullable=True)
    ncbi_family = Column(Text, nullable=True)
    busco_dataset_name = Column(Text, nullable=True)
    augustus_dataset_name = Column(Text, nullable=True)
    bpa_json = Column(JSONB, nullable=True)
    taxonomy_lineage_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )

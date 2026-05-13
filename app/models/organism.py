from sqlalchemy import Column, DateTime, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.db.session import Base


class Organism(Base):
    """
    Organism model for storing taxonomic information.

    This model corresponds to the 'organism' table in the database.
    """

    __tablename__ = "organism"

    taxon_id = Column(Integer, primary_key=True)
    bpa_scientific_name = Column(Text, nullable=True)
    bpa_genus = Column(Text, nullable=True)
    bpa_species = Column(Text, nullable=True)
    bpa_common_name = Column(Text, nullable=True)
    bpa_infraspecific_epithet = Column(Text, nullable=True)
    bpa_culture_or_strain_id = Column(Text, nullable=True)
    bpa_authority = Column(Text, nullable=True)
    scientific_name = Column(Text, nullable=True)
    atol_scientific_name = Column(Text, nullable=True)
    bpa_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    taxonomy_info = relationship(
        "TaxonomyInfo",
        back_populates="organism",
        uselist=False,
        cascade="all, delete-orphan",
    )

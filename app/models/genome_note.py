import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.session import Base


class GenomeNote(Base):
    """
    GenomeNote model for storing versioned genome notes linked to assemblies.

    Each organism can have multiple draft versions but only one published version.
    Versions are auto-incremented per organism.

    This model corresponds to the 'genome_note' table in the database.
    """

    __tablename__ = "genome_note"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organism_key = Column(
        Text, ForeignKey("organism.grouping_key", ondelete="CASCADE"), nullable=False
    )
    assembly_id = Column(
        UUID(as_uuid=True), ForeignKey("assembly.id", ondelete="CASCADE"), nullable=False
    )

    # Versioning: auto-increment per organism
    version = Column(Integer, nullable=False)

    # Content and metadata
    title = Column(Text, nullable=False)
    note_url = Column(Text, nullable=False)

    # Publication status
    is_published = Column(Boolean, nullable=False, default=False)
    published_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    organism = relationship("Organism", backref="genome_notes")
    assembly = relationship("Assembly", backref="genome_notes")

    # Table constraints
    __table_args__ = (
        UniqueConstraint("organism_key", "version", name="uq_genome_note_organism_version"),
        # Note: The partial unique index for published notes is created in the schema.sql
        # CREATE UNIQUE INDEX uq_genome_note_one_published_per_organism ON genome_note (organism_key) WHERE is_published = TRUE;
    )

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.session import Base


class GenomeNote(Base):
    """
    GenomeNote model for storing notes and metadata about genomes.
    
    This model corresponds to the 'genome_note' table in the database.
    """
    __tablename__ = "genome_note"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    genome_note_assembly_id = Column(UUID(as_uuid=True), ForeignKey("assembly.id"), unique=True, nullable=True)
    tax_id = Column(Integer, ForeignKey("organism.tax_id"), nullable=False)
    is_published = Column(Boolean, nullable=False, default=False)
    title = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    # Relationships
    organism = relationship("Organism", backref="genome_notes")
    
    # Table constraints
    __table_args__ = (
        # This is a simplified version of the SQL constraint:
        # CREATE UNIQUE INDEX uq_genome_note_one_published_per_organism ON genome_note (tax_id) WHERE is_published = TRUE;
        # SQLAlchemy doesn't directly support WHERE clauses in constraints, so this would need custom SQL
    )


class GenomeNoteAssembly(Base):
    """
    GenomeNoteAssembly model for linking genome notes to assemblies.
    
    This model corresponds to the 'genome_note_assembly' table in the database.
    """
    __tablename__ = "genome_note_assembly"
    
    # Composite primary key fields
    genome_note_id = Column(UUID(as_uuid=True), ForeignKey("genome_note.id"), nullable=False, primary_key=True)
    assembly_id = Column(UUID(as_uuid=True), ForeignKey("assembly.id"), nullable=False, primary_key=True)
    
    # Relationships
    genome_note = relationship("GenomeNote", backref="genome_note_assemblies")
    assembly = relationship("Assembly", backref="genome_note_assemblies")

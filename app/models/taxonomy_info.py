from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.db.session import Base


class TaxonomyInfo(Base):
    __tablename__ = "taxonomy_info"

    taxon_id = Column(
        Integer, ForeignKey("organism.taxon_id", ondelete="CASCADE"), primary_key=True
    )
    ncbi_taxon_id = Column(Integer, nullable=True)
    ncbi_rank = Column(Text, nullable=True)
    ncbi_scientific_name = Column(Text, nullable=True)
    ncbi_authority = Column(Text, nullable=True)
    ncbi_common_name = Column(Text, nullable=True)
    ncbi_class = Column(Text, nullable=True)
    ncbi_order = Column(Text, nullable=True)
    ncbi_family = Column(Text, nullable=True)
    ncbi_lineage = Column(JSONB, nullable=True)
    ncbi_tax_string = Column(Text, nullable=True)
    ncbi_full_lineage = Column(Text, nullable=True)
    ncbi_last_synced_at = Column(DateTime(timezone=True), nullable=True)
    busco_odb10_dataset_name = Column(Text, nullable=True)
    busco_odb12_dataset_name = Column(Text, nullable=True)
    find_plastid = Column(Boolean, nullable=True)
    hic_motif = Column(Text, nullable=True)
    mitochondrial_genetic_code_id = Column(Integer, nullable=True)
    mitohifi_reference_species = Column(Text, nullable=True)
    oatk_hmm_name = Column(Text, nullable=True)
    augustus_dataset_name = Column(Text, nullable=True)
    genetic_code_id = Column(Integer, nullable=True)

    organism = relationship("Organism", back_populates="taxonomy_info")

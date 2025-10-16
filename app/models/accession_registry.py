import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, Enum as SQLAlchemyEnum, BigInteger
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.session import Base


class AccessionRegistry(Base):
    """
    AccessionRegistry model for storing accession information for various entities.
    
    This model corresponds to the 'accession_registry' table in the database.
    """
    __tablename__ = "accession_registry"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    authority = Column(SQLAlchemyEnum("ENA", "NCBI", "DDBJ", name="authority_type"), nullable=False)
    accession = Column(Text, nullable=False, unique=True)
    secondary_accession = Column(Text, nullable=True)
    entity_type = Column(SQLAlchemyEnum("organism", "sample", "experiment", "read", "assembly", "bioproject", name="entity_type"), nullable=False)
    entity_id = Column(BigInteger, nullable=False)
    accepted_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now(timezone.utc))
    created_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    # Table constraints
    __table_args__ = (
        # These are simplified versions of the SQL constraints:
        # UNIQUE (authority, entity_type, entity_id)
        # UNIQUE (authority, accession)
    )

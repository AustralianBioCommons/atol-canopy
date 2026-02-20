import uuid

from sqlalchemy import Column, DateTime, Text, func
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.dialects.postgresql import UUID

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
    entity_type = Column(
        SQLAlchemyEnum(
            "organism", "sample", "experiment", "read", "assembly", "project", name="entity_type"
        ),
        nullable=False,
    )
    entity_id = Column(UUID(as_uuid=True), nullable=False)
    accepted_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Table constraints
    __table_args__ = (
        # These are simplified versions of the SQL constraints:
        # UNIQUE (authority, entity_type, entity_id)
        # UNIQUE (authority, accession)
    )

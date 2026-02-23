from sqlalchemy import Column, DateTime, Text, func

from app.db.session import Base


class BPAInitiative(Base):
    """
    BPA Initiative model for storing information about BPA initiatives.

    This model corresponds to the 'bpa_initiative' table in the database.
    """

    __tablename__ = "bpa_initiative"

    project_code = Column(Text, primary_key=True)
    title = Column(Text, nullable=False)
    url = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

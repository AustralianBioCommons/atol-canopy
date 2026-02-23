import uuid
from typing import List

from sqlalchemy import ARRAY, Boolean, Column, DateTime, Text, func
from sqlalchemy.dialects.postgresql import UUID
from app.db.session import Base


class User(Base):
    """
    User model for authentication and authorization.

    This model corresponds to the 'users' table in the database.
    """

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(Text, unique=True, nullable=False)
    email = Column(Text, unique=True, nullable=True)
    hashed_password = Column(Text, nullable=False)
    full_name = Column(Text, nullable=True)
    roles = Column(ARRAY(Text), nullable=False, default=[])
    is_active = Column(Boolean, nullable=False, default=True)
    is_superuser = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

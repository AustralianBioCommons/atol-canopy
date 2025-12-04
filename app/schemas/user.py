from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field
from pydantic import ConfigDict


class UserBase(BaseModel):
    """Base User schema with common attributes."""
    username: str
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool = True
    roles: List[str] = []


class UserCreate(UserBase):
    """Schema for creating a new user."""
    password: str


class UserUpdate(BaseModel):
    """Schema for updating an existing user."""
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    roles: Optional[List[str]] = None


class UserInDBBase(UserBase):
    """Base schema for User in DB, includes id and timestamps."""
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class User(UserInDBBase):
    """Schema for returning user information."""
    pass


class UserInDB(UserInDBBase):
    """Schema for User in DB, includes hashed_password."""
    hashed_password: str


class Token(BaseModel):
    """Schema for JWT token."""
    access_token: str
    token_type: str


class TokenResponse(Token):
    """Schema for JWT token response with refresh token."""
    refresh_token: str


class RefreshRequest(BaseModel):
    """Schema for refresh token request."""
    refresh_token: str


class TokenPayload(BaseModel):
    """Schema for JWT token payload."""
    sub: Optional[str] = None

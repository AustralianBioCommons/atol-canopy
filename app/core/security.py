from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Union
import hashlib
import secrets

import bcrypt
from jose import jwt

from app.core.settings import settings

# TODO must enforce same byte limitation at input validation
BCRYPT_MAX_BYTES = 72

def _bcrypt_bytes(password: str) -> bytes:
     return password.encode("utf-8")[:BCRYPT_MAX_BYTES]

def create_access_token(
    subject: Union[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a new JWT access token.
    
    Args:
        subject: Subject of the token (typically user ID)
        expires_delta: Optional expiration time delta
        
    Returns:
        str: Encoded JWT token
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(
        to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hash.
    
    Args:
        plain_password: Plain text password
        hashed_password: Hashed password
        
    Returns:
        bool: True if password matches hash
    """
    try:
        return bcrypt.checkpw(_bcrypt_bytes(plain_password), hashed_password.encode("utf-8"))
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """
    Hash a password.
    
    Args:
        password: Plain text password
        
    Returns:
        str: Hashed password
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(_bcrypt_bytes(password), salt)
    return hashed.decode("utf-8")


def generate_refresh_token(length: int = 32) -> str:
    """
    Generate a secure random string for use as a refresh token.
    
    Args:
        length: Length of the token in bytes
        
    Returns:
        str: Secure random string
    """
    return secrets.token_urlsafe(length)


def hash_token(token: str) -> str:
    """
    Hash a token for secure storage in the database.
    
    Args:
        token: Plain text token
        
    Returns:
        str: Hashed token
    """
    return hashlib.sha256(token.encode()).hexdigest()

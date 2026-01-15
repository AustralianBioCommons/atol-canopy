from typing import Annotated, List, Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.core.settings import settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import TokenPayload

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")


def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> User:
    """
    Get the current user from the token.

    Args:
        db: Database session
        token: JWT token

    Returns:
        User: Current user

    Raises:
        HTTPException: If token is invalid or user is not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        token_data = TokenPayload(**payload)
        if token_data.sub is None:
            raise credentials_exception
    except (JWTError, ValidationError):
        raise credentials_exception

    user = db.query(User).filter(User.id == token_data.sub).first()
    if not user:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return user


def get_current_active_user(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    """
    Get the current active user.

    Args:
        current_user: Current user

    Returns:
        User: Current active user

    Raises:
        HTTPException: If user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return current_user


def get_current_active_superuser(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    """
    Get the current active superuser.

    Args:
        current_user: Current user

    Returns:
        User: Current active superuser

    Raises:
        HTTPException: If user is not a superuser
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges",
        )
    return current_user


# Alias for get_current_active_superuser for backward compatibility
get_current_superuser = get_current_active_superuser


def require_role(current_user: User, required_roles: List[str]) -> None:
    """
    Check if the user has the required roles.

    Args:
        current_user: Current user
        required_roles: List of required roles

    Raises:
        HTTPException: If user doesn't have the required roles
    """
    if current_user.is_superuser:
        return

    for role in required_roles:
        if role in current_user.roles:
            return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="The user doesn't have the required roles",
    )


def has_role(required_roles: List[str]):
    """
    Check if the user has the required roles.

    Args:
        required_roles: List of required roles

    Returns:
        Function: Dependency function to check roles
    """

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        for role in required_roles:
            if role in current_user.roles or current_user.is_superuser:
                return current_user
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

    return role_checker


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """
    Authenticate a user with username and password.

    Args:
        db: Database session
        username: Username
        password: Plain text password

    Returns:
        Optional[User]: User if authentication is successful, None otherwise
    """
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

from datetime import datetime, timedelta, timezone
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.dependencies import authenticate_user, get_current_user
from app.core.security import create_access_token, generate_refresh_token, hash_token
from app.core.settings import settings
from app.db.session import get_db
from app.models.token import RefreshToken
from app.models.user import User
from app.schemas.user import Token, TokenResponse, RefreshRequest

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login_access_token(
    db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """
    OAuth2 compatible token login, get an access token and refresh token for future requests.
    
    Args:
        db: Database session
        form_data: Form data with username and password
        
    Returns:
        TokenResponse: Access token and refresh token
        
    Raises:
        HTTPException: If authentication fails
    """
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    # Create access token with expiration
    access_token_expires = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        user.id, expires_delta=access_token_expires
    )
    
    # Create refresh token
    refresh_token_expires = timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_token_value = generate_refresh_token()
    
    # Store refresh token in database
    db_refresh_token = RefreshToken(
        id=uuid.uuid4(),
        token_hash=hash_token(refresh_token_value),
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + refresh_token_expires,
        revoked=False
    )
    
    db.add(db_refresh_token)
    db.commit()
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token_value,
        "token_type": "bearer",
    }


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    request: RefreshRequest, db: Session = Depends(get_db)
) -> Any:
    """
    Get a new access token using a refresh token.
    
    Args:
        request: Refresh token request
        db: Database session
        
    Returns:
        TokenResponse: New access token and refresh token
        
    Raises:
        HTTPException: If refresh token is invalid or expired
    """
    # Find the token in the database
    token_hash = hash_token(request.refresh_token)
    stored_token = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash,
        RefreshToken.expires_at > datetime.now(timezone.utc),
        RefreshToken.revoked == False
    ).first()
    
    if not stored_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get the user
    user = db.query(User).filter(User.id == stored_token.user_id).first()
    if not user or not user.is_active:
        # Revoke token if user is invalid or inactive
        stored_token.revoked = True
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User inactive or deleted",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Implement refresh token rotation for better security
    # This revokes the old token and creates a new one
    stored_token.revoked = True
    
    # Create new tokens
    access_token_expires = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_token_expires = timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    
    # Create new access token
    access_token = create_access_token(
        user.id, expires_delta=access_token_expires
    )
    
    # Create new refresh token
    new_refresh_token_value = generate_refresh_token()
    new_refresh_token = RefreshToken(
        id=uuid.uuid4(),
        token_hash=hash_token(new_refresh_token_value),
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + refresh_token_expires,
        revoked=False
    )
    
    db.add(new_refresh_token)
    db.commit()
    
    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token_value,
        "token_type": "bearer",
    }


@router.post("/logout")
def logout(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Logout a user by revoking all their refresh tokens.
    
    Args:
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        dict: Success message
    """
    # Revoke all refresh tokens for the user
    db.query(RefreshToken).filter(
        RefreshToken.user_id == current_user.id,
        RefreshToken.revoked == False
    ).update({RefreshToken.revoked: True})
    
    db.commit()
    
    return {"message": "Successfully logged out"}

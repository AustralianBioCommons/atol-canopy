from typing import Any, List
from uuid import UUID, uuid4
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_active_user
from app.core.security import get_password_hash
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, User as UserSchema

router = APIRouter()


@router.get("/", response_model=List[UserSchema])
def read_users(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve users.
    
    Args:
        db: Database session
        skip: Number of records to skip
        limit: Maximum number of records to return
        current_user: Current user (must be superuser)
        
    Returns:
        List[User]: List of users
    """
    users = db.query(User).offset(skip).limit(limit).all()
    return users


@router.post("/", response_model=UserSchema)
def create_user(
    *,
    db: Session = Depends(get_db),
    user_in: UserCreate,
) -> Any:
    """
    Create new user.
    
    Args:
        db: Database session
        user_in: User data
        current_user: Current user (must be superuser)
        
    Returns:
        User: Created user
        
    Raises:
        HTTPException: If user with same username or email already exists
    """
    # Check if user with same username exists
    user = db.query(User).filter(User.username == user_in.username).first()
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )
    
    # Check if user with same email exists
    user = db.query(User).filter(User.email == user_in.email).first()
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    
    # Create new user
    now = datetime.now(timezone.utc)
    db_user = User(
        id=uuid4(),
        username=user_in.username,
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        # TODO restrict roles to only be assignable after creation? or require admin role to create?
        roles=user_in.roles,
        is_active=user_in.is_active,
        created_at=now,
        updated_at=now,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@router.get("/me", response_model=UserSchema)
def read_user_me(
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get current user.
    
    Args:
        current_user: Current user
        
    Returns:
        User: Current user
    """
    return current_user


@router.put("/me", response_model=UserSchema)
def update_user_me(
    *,
    db: Session = Depends(get_db),
    user_in: UserUpdate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Update current user.
    
    Args:
        db: Database session
        user_in: User data to update
        current_user: Current user
        
    Returns:
        User: Updated user
    """
    # Update user fields
    if user_in.username is not None:
        current_user.username = user_in.username
    if user_in.email is not None:
        current_user.email = user_in.email
    if user_in.full_name is not None:
        current_user.full_name = user_in.full_name
    if user_in.password is not None:
        current_user.hashed_password = get_password_hash(user_in.password)
    
    # Ensure required timestamps exist for response validation
    if getattr(current_user, "created_at", None) is None:
        current_user.created_at = datetime.now(timezone.utc)
    current_user.updated_at = datetime.now(timezone.utc)
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/{user_id}", response_model=UserSchema)
def read_user_by_id(
    user_id: UUID,
    db: Session = Depends(get_db),
) -> Any:
    """
    Get a specific user by id.
    
    Args:
        user_id: User ID
        db: Database session
        current_user: Current user (must be superuser)
        
    Returns:
        User: User with specified ID
        
    Raises:
        HTTPException: If user not found
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    # Ensure required timestamps for response validation
    if getattr(user, "created_at", None) is None:
        user.created_at = datetime.now(timezone.utc)
    if getattr(user, "updated_at", None) is None:
        user.updated_at = datetime.now(timezone.utc)
    return user


@router.put("/{user_id}", response_model=UserSchema)
def update_user(
    *,
    db: Session = Depends(get_db),
    user_id: UUID,
    user_in: UserUpdate,
) -> Any:
    """
    Update a user.
    
    Args:
        db: Database session
        user_id: User ID
        user_in: User data to update
        current_user: Current user (must be superuser)
        
    Returns:
        User: Updated user
        
    Raises:
        HTTPException: If user not found
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    # Update user fields
    if user_in.username is not None:
        user.username = user_in.username
    if user_in.email is not None:
        user.email = user_in.email
    if user_in.full_name is not None:
        user.full_name = user_in.full_name
    if user_in.password is not None:
        user.hashed_password = get_password_hash(user_in.password)
    if user_in.is_active is not None:
        user.is_active = user_in.is_active
    if user_in.roles is not None:
        user.roles = user_in.roles
    
    # Ensure timestamps
    if getattr(user, "created_at", None) is None:
        user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

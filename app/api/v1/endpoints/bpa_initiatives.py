from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import (
    get_current_active_user,
    get_current_superuser,
    get_db,
    require_role,
)
from app.models.bpa_initiative import BPAInitiative
from app.models.user import User
from app.schemas.bpa_initiative import (
    BPAInitiative as BPAInitiativeSchema,
    BPAInitiativeCreate,
    BPAInitiativeUpdate,
)

router = APIRouter()


@router.get("/", response_model=List[BPAInitiativeSchema])
def read_bpa_initiatives(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Retrieve BPA initiatives.
    """
    # All users can read BPA initiatives
    initiatives = db.query(BPAInitiative).offset(skip).limit(limit).all()
    return initiatives


@router.post("/", response_model=BPAInitiativeSchema)
def create_bpa_initiative(
    *,
    db: Session = Depends(get_db),
    initiative_in: BPAInitiativeCreate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Create new BPA initiative.
    """
    # Only users with 'curator' or 'admin' role can create BPA initiatives
    require_role(current_user, ["curator", "admin"])
    
    initiative = BPAInitiative(
        project_code=getattr(initiative_in, "project_code", None),
        title=getattr(initiative_in, "title", None),
        url=getattr(initiative_in, "url", None),
    )
    db.add(initiative)
    db.commit()
    db.refresh(initiative)
    return initiative


@router.get("/{initiative_id}", response_model=BPAInitiativeSchema)
def read_bpa_initiative(
    *,
    db: Session = Depends(get_db),
    initiative_id: str,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get BPA initiative by ID.
    """
    # All users can read BPA initiative details
    initiative = db.query(BPAInitiative).filter(BPAInitiative.project_code == initiative_id).first()
    if not initiative:
        raise HTTPException(status_code=404, detail="BPA initiative not found")
    return initiative


@router.put("/{initiative_id}", response_model=BPAInitiativeSchema)
def update_bpa_initiative(
    *,
    db: Session = Depends(get_db),
    initiative_id: str,
    initiative_in: BPAInitiativeUpdate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Update a BPA initiative.
    """
    # Only users with 'curator' or 'admin' role can update BPA initiatives
    require_role(current_user, ["curator", "admin"])
    
    initiative = db.query(BPAInitiative).filter(BPAInitiative.project_code == initiative_id).first()
    if not initiative:
        raise HTTPException(status_code=404, detail="BPA initiative not found")
    
    update_data = initiative_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(initiative, field, value)
    
    db.add(initiative)
    db.commit()
    db.refresh(initiative)
    return initiative


@router.delete("/{initiative_id}", response_model=BPAInitiativeSchema)
def delete_bpa_initiative(
    *,
    db: Session = Depends(get_db),
    initiative_id: str,
    current_user: User = Depends(get_current_superuser),
) -> Any:
    """
    Delete a BPA initiative.
    """
    # Only superusers can delete BPA initiatives
    initiative = db.query(BPAInitiative).filter(BPAInitiative.project_code == initiative_id).first()
    if not initiative:
        raise HTTPException(status_code=404, detail="BPA initiative not found")
    
    db.delete(initiative)
    db.commit()
    return initiative

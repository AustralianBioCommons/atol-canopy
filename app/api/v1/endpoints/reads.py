import uuid
from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_active_user, get_db
from app.core.pagination import Pagination, apply_pagination, pagination_params
from app.core.policy import policy
from app.models.read import Read
from app.models.user import User
from app.schemas.read import (
    Read as ReadSchema,
)
from app.schemas.read import (
    ReadCreate,
    ReadUpdate,
)

router = APIRouter()

_READ_MUTABLE_FIELDS = {
    column.name
    for column in Read.__table__.columns
    if column.name not in {"id", "created_at", "updated_at"}
}


@router.get("/", response_model=List[ReadSchema])
def read_reads(
    db: Session = Depends(get_db),
    pagination: Pagination = Depends(pagination_params),
    experiment_id: Optional[UUID] = Query(None, description="Filter by experiment ID"),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Retrieve reads.
    """
    query = db.query(Read)
    if experiment_id:
        query = query.filter(Read.experiment_id == experiment_id)

    reads = apply_pagination(query, pagination).all()
    return reads


@router.post("/", response_model=ReadSchema)
@policy("reads:create")
def create_read(
    *,
    db: Session = Depends(get_db),
    read_in: ReadCreate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Create new read.
    """
    read_id = uuid.uuid4()

    read_data = read_in.model_dump(exclude_unset=True)
    read_kwargs = {k: v for k, v in read_data.items() if k in _READ_MUTABLE_FIELDS}
    if "optional_file" in read_kwargs and read_kwargs["optional_file"] is not None:
        val = read_kwargs["optional_file"]
        if not isinstance(val, bool):
            read_kwargs["optional_file"] = str(val).lower() in ("true", "1", "yes")

    read = Read(id=read_id, **read_kwargs)
    db.add(read)
    db.commit()
    db.refresh(read)
    return read


@router.get("/{read_id}", response_model=ReadSchema)
def read_read(
    *,
    db: Session = Depends(get_db),
    read_id: UUID,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get read by ID.
    """
    read = db.query(Read).filter(Read.id == read_id).first()
    if not read:
        raise HTTPException(status_code=404, detail="Read not found")
    return read


@router.put("/{read_id}", response_model=ReadSchema)
@policy("reads:update")
def update_read(
    *,
    db: Session = Depends(get_db),
    read_id: UUID,
    read_in: ReadUpdate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Update a read.
    """
    read = db.query(Read).filter(Read.id == read_id).first()
    if not read:
        raise HTTPException(status_code=404, detail="Read not found")

    read_data = read_in.model_dump(exclude_unset=True)
    for field, value in read_data.items():
        if field not in _READ_MUTABLE_FIELDS:
            continue
        if field == "optional_file" and value is not None and not isinstance(value, bool):
            value = str(value).lower() in ("true", "1", "yes")
        setattr(read, field, value)

    db.add(read)
    db.commit()
    db.refresh(read)
    return read


@router.delete("/{read_id}", response_model=ReadSchema)
@policy("reads:delete")
def delete_read(
    *,
    db: Session = Depends(get_db),
    read_id: UUID,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Delete a read.
    """
    read = db.query(Read).filter(Read.id == read_id).first()
    if not read:
        raise HTTPException(status_code=404, detail="Read not found")

    db.delete(read)
    db.commit()
    return read

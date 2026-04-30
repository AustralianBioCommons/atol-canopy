import uuid
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_active_user, get_db
from app.core.pagination import Pagination, apply_pagination, pagination_params
from app.core.policy import policy
from app.models.organism import Organism
from app.models.user import User
from app.schemas.aggregate import OrganismSubmissionJsonResponse
from app.schemas.bulk_import import BulkImportResponse
from app.schemas.organism import (
    Organism as OrganismSchema,
)
from app.schemas.organism import (
    OrganismCreate,
    OrganismUpdate,
)
from app.services.organism_service import organism_service

router = APIRouter()


@router.get("/", response_model=List[OrganismSchema])
def read_organisms(
    db: Session = Depends(get_db),
    pagination: Pagination = Depends(pagination_params),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Retrieve organisms.
    """
    # All users can read organisms
    query = db.query(Organism)
    query = apply_pagination(query, pagination)
    return query.all()


@router.get("/{taxon_id}/experiments")
@policy("organisms:read_sensitive")
def get_experiments_for_organism(
    *,
    db: Session = Depends(get_db),
    taxon_id: int,
    includeReads: bool = Query(False, description="Include reads for each experiment"),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Return all experiments for the organism, and optionally all reads for each experiment when includeReads is true.
    """
    data = organism_service.get_experiments_for_organism(
        db, taxon_id=taxon_id, include_reads=includeReads
    )
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organism with taxon_id '{taxon_id}' not found",
        )
    return data


@router.get("/submissions/{taxon_id}", response_model=OrganismSubmissionJsonResponse)
@policy("organisms:read_sensitive")
def get_organism_prepared_payload(
    *,
    db: Session = Depends(get_db),
    taxon_id: int,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get all prepared_payload data for samples, experiments, and reads related to a specific organism.
    """
    data = organism_service.get_organism_prepared_payload(db, taxon_id=taxon_id)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organism with taxon_id '{taxon_id}' not found",
        )
    return data


@router.post("/", response_model=OrganismSchema)
@policy("organisms:create")
def create_organism(
    *,
    db: Session = Depends(get_db),
    organism_in: OrganismCreate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Create new organism.
    """
    try:
        organism = organism_service.create_organism(db, organism_in=organism_in)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return organism


@router.get("/{taxon_id}", response_model=OrganismSchema)
def read_organism(
    *,
    db: Session = Depends(get_db),
    taxon_id: int,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get organism by taxon_id.
    """
    # All users can read organism details
    organism = organism_service.get_by_taxon_id(db, taxon_id)
    if not organism:
        raise HTTPException(status_code=404, detail="Organism not found")
    return organism


@router.patch("/{taxon_id}", response_model=OrganismSchema)
@policy("organisms:update")
def update_organism(
    *,
    db: Session = Depends(get_db),
    taxon_id: int,
    organism_in: OrganismUpdate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Update an organism.
    """
    organism = organism_service.update_organism(db, taxon_id=taxon_id, organism_in=organism_in)
    if not organism:
        raise HTTPException(status_code=404, detail="Organism not found")
    return organism


@router.delete("/{taxon_id}", response_model=OrganismSchema)
@policy("organisms:delete")
def delete_organism(
    *,
    db: Session = Depends(get_db),
    taxon_id: int,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Delete an organism.
    """
    organism = organism_service.delete_organism(db, taxon_id=taxon_id)
    if not organism:
        raise HTTPException(status_code=404, detail="Organism not found")
    return organism


@router.post("/bulk-import", response_model=BulkImportResponse)
@policy("organisms:bulk_import")
def bulk_import_organisms(
    *,
    db: Session = Depends(get_db),
    organisms_data: Dict[
        str, Dict[str, Any]
    ],  # Accept direct dictionary format from unique_organisms.json
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Bulk import organisms from a dictionary keyed by taxon_id.

    The request body should directly match the format of the JSON file in data/unique_organisms.json,
    which is a dictionary keyed by taxon_id without a wrapping 'organisms' key.
    """
    result = organism_service.bulk_import_organisms(db, organisms_data=organisms_data)
    return result

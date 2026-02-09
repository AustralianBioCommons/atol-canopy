import uuid
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import (
    get_current_active_user,
    get_current_superuser,
    get_db,
    require_role,
)
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
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Retrieve organisms.
    """
    # All users can read organisms
    return organism_service.list_organisms(db, skip=skip, limit=limit)


@router.get("/{grouping_key}/experiments")
def get_experiments_for_organism(
    *,
    db: Session = Depends(get_db),
    grouping_key: str,
    includeReads: bool = Query(False, description="Include reads for each experiment"),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Return all experiments for the organism, and optionally all reads for each experiment when includeReads is true.
    """
    # Admin, curator, broker and genome_launcher can get expanded organism data
    require_role(current_user, ["admin", "curator", "broker", "genome_launcher"])
    data = organism_service.get_experiments_for_organism(
        db, grouping_key=grouping_key, include_reads=includeReads
    )
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organism with grouping key '{grouping_key}' not found",
        )
    return data


@router.get("/submissions/{grouping_key}", response_model=OrganismSubmissionJsonResponse)
def get_organism_prepared_payload(
    *,
    db: Session = Depends(get_db),
    grouping_key: str,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get all prepared_payload data for samples, experiments, and reads related to a specific organism.grouping_key.
    """
    # Admin, curator, broker and genome_launcher can get prepared_payload data
    require_role(current_user, ["admin", "curator", "broker", "genome_launcher"])
    data = organism_service.get_organism_prepared_payload(db, grouping_key=grouping_key)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organism with grouping key '{grouping_key}' not found",
        )
    return data


@router.post("/", response_model=OrganismSchema)
def create_organism(
    *,
    db: Session = Depends(get_db),
    organism_in: OrganismCreate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Create new organism.
    """
    # Only users with 'curator' or 'admin' role can create organisms
    require_role(current_user, ["curator", "admin"])
    try:
        organism = organism_service.create_organism(db, organism_in=organism_in)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return organism


@router.get("/{grouping_key}", response_model=OrganismSchema)
def read_organism(
    *,
    db: Session = Depends(get_db),
    grouping_key: str,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get organism by grouping_key.
    """
    # All users can read organism details
    organism = organism_service.get_by_grouping_key(db, grouping_key)
    if not organism:
        raise HTTPException(status_code=404, detail="Organism not found")
    return organism


@router.patch("/{grouping_key}", response_model=OrganismSchema)
def update_organism(
    *,
    db: Session = Depends(get_db),
    grouping_key: str,
    organism_in: OrganismUpdate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Update an organism.
    """
    # Only users with 'curator' or 'admin' role can update organisms
    require_role(current_user, ["curator", "admin"])
    organism = organism_service.update_organism(
        db, grouping_key=grouping_key, organism_in=organism_in
    )
    if not organism:
        raise HTTPException(status_code=404, detail="Organism not found")
    return organism


@router.delete("/{grouping_key}", response_model=OrganismSchema)
def delete_organism(
    *,
    db: Session = Depends(get_db),
    grouping_key: str,
    current_user: User = Depends(get_current_superuser),
) -> Any:
    """
    Delete an organism.
    """
    # Only users with 'superuser' or 'admin' role can delete organisms
    require_role(current_user, ["admin", "superuser"])
    organism = organism_service.delete_organism(db, grouping_key=grouping_key)
    if not organism:
        raise HTTPException(status_code=404, detail="Organism not found")
    return organism


@router.post("/bulk-import", response_model=BulkImportResponse)
def bulk_import_organisms(
    *,
    db: Session = Depends(get_db),
    organisms_data: Dict[
        str, Dict[str, Any]
    ],  # Accept direct dictionary format from unique_organisms.json
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Bulk import organisms from a dictionary keyed by organism_grouping_key.

    The request body should directly match the format of the JSON file in data/unique_organisms.json,
    which is a dictionary keyed by organism_grouping_key without a wrapping 'organisms' key.
    """
    # Only users with 'curator' or 'admin' role can import organisms
    require_role(current_user, ["curator", "admin"])
    result = organism_service.bulk_import_organisms(db, organisms_data=organisms_data)
    return result

from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_active_user, get_db
from app.core.pagination import Pagination, apply_pagination, pagination_params
from app.core.policy import policy
from app.models.taxonomy_info import TaxonomyInfo
from app.models.user import User
from app.schemas.bulk_import import (
    BulkImportResponse,
    BulkNcbiRefreshRequest,
    BulkTaxonomyInfoImport,
)
from app.schemas.taxonomy_info import (
    TaxonomyInfo as TaxonomyInfoSchema,
)
from app.schemas.taxonomy_info import (
    TaxonomyInfoCreate,
    TaxonomyInfoUpdate,
)
from app.services.taxonomy_info_service import taxonomy_info_service

router = APIRouter()


@router.get("/", response_model=List[TaxonomyInfoSchema])
def list_taxonomy_info(
    db: Session = Depends(get_db),
    pagination: Pagination = Depends(pagination_params),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """List taxonomy info records."""
    query = db.query(TaxonomyInfo)
    query = apply_pagination(query, pagination)
    return query.all()


@router.post("/bulk-import", response_model=BulkImportResponse)
@policy("taxonomy_info:bulk_import")
def bulk_import_taxonomy_info(
    *,
    db: Session = Depends(get_db),
    data: BulkTaxonomyInfoImport,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Bulk import taxonomy info from a dictionary keyed by taxon_id.

    Insert-only for fully-synced rows — existing rows that never completed NCBI sync
    are retried so a rerun can repair prior partial imports.
    The taxon_id key must reference an existing organism.
    """
    return taxonomy_info_service.bulk_import(db, data=data.root)


@router.post("/bulk-upsert", response_model=BulkImportResponse)
@policy("taxonomy_info:bulk_upsert")
def bulk_upsert_taxonomy_info(
    *,
    db: Session = Depends(get_db),
    data: BulkTaxonomyInfoImport,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Bulk upsert taxonomy info from a dictionary keyed by taxon_id.

    Inserts new rows and updates existing ones. Re-fetches NCBI data for all rows.
    The taxon_id key must reference an existing organism.
    """
    return taxonomy_info_service.bulk_upsert(db, data=data.root)


@router.post("/bulk-ncbi-refresh", response_model=BulkImportResponse)
@policy("taxonomy_info:bulk_ncbi_refresh")
def bulk_ncbi_refresh_taxonomy_info(
    *,
    db: Session = Depends(get_db),
    data: BulkNcbiRefreshRequest,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Re-sync NCBI taxonomy fields for existing taxonomy_info rows.

    Only updates ncbi_* columns — upstream fields are left unchanged.
    Rows that do not yet have a taxonomy_info record are skipped.
    """
    return taxonomy_info_service.bulk_ncbi_refresh(db, taxon_ids=data.taxon_ids)


@router.get("/{taxon_id}", response_model=TaxonomyInfoSchema)
def get_taxonomy_info(
    *,
    db: Session = Depends(get_db),
    taxon_id: int,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Get taxonomy info by taxon_id."""
    ti = taxonomy_info_service.get(db, taxon_id)
    if not ti:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TaxonomyInfo not found")
    return ti


@router.post("/", response_model=TaxonomyInfoSchema, status_code=status.HTTP_201_CREATED)
@policy("taxonomy_info:create")
def create_taxonomy_info(
    *,
    db: Session = Depends(get_db),
    ti_in: TaxonomyInfoCreate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Create taxonomy info for an existing organism."""
    try:
        return taxonomy_info_service.create(db, ti_in=ti_in)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.patch("/{taxon_id}", response_model=TaxonomyInfoSchema)
@policy("taxonomy_info:update")
def update_taxonomy_info(
    *,
    db: Session = Depends(get_db),
    taxon_id: int,
    ti_in: TaxonomyInfoUpdate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Update taxonomy info by taxon_id."""
    ti = taxonomy_info_service.update(db, taxon_id=taxon_id, ti_in=ti_in)
    if not ti:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TaxonomyInfo not found")
    return ti


@router.delete("/{taxon_id}", response_model=TaxonomyInfoSchema)
@policy("taxonomy_info:delete")
def delete_taxonomy_info(
    *,
    db: Session = Depends(get_db),
    taxon_id: int,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """Delete taxonomy info by taxon_id."""
    ti = taxonomy_info_service.delete(db, taxon_id=taxon_id)
    if not ti:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TaxonomyInfo not found")
    return ti

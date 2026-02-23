from __future__ import annotations

from dataclasses import dataclass

from fastapi import Query
from sqlalchemy.orm import Query as SAQuery


@dataclass(frozen=True)
class Pagination:
    offset: int
    limit: int


def pagination_params(
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Max records to return"),
) -> Pagination:
    return Pagination(offset=offset, limit=limit)


def apply_pagination(query: SAQuery, pagination: Pagination) -> SAQuery:
    return query.offset(pagination.offset).limit(pagination.limit)

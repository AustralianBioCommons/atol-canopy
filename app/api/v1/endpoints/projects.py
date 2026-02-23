from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_active_user, get_db
from app.core.pagination import Pagination, apply_pagination, pagination_params
from app.core.policy import policy
from app.models.project import Project
from app.models.user import User
from app.schemas.project import (
    Project as ProjectSchema,
)
from app.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
)

router = APIRouter()


@router.get("/", response_model=List[ProjectSchema])
def read_projects(
    db: Session = Depends(get_db),
    pagination: Pagination = Depends(pagination_params),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Retrieve projects.
    """
    # All users can read projects
    projects = apply_pagination(db.query(Project), pagination).all()
    return projects


@router.post("/", response_model=ProjectSchema)
@policy("projects:create")
def create_project(
    *,
    db: Session = Depends(get_db),
    project_in: ProjectCreate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Create new project.
    """
    project = Project(
        project_accession=project_in.project_accession,
        alias=project_in.alias,
        alias_md5=project_in.alias_md5,
        study_name=project_in.study_name,
        new_study_type=project_in.new_study_type,
        study_abstract=project_in.study_abstract,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectSchema)
def read_project(
    *,
    db: Session = Depends(get_db),
    project_id: UUID,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get project by ID.
    """
    # All users can read project details
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.put("/{project_id}", response_model=ProjectSchema)
@policy("projects:update")
def update_project(
    *,
    db: Session = Depends(get_db),
    project_id: UUID,
    project_in: ProjectUpdate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Update a project.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    update_data = project_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", response_model=ProjectSchema)
@policy("projects:delete")
def delete_project(
    *,
    db: Session = Depends(get_db),
    project_id: UUID,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Delete a project.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    db.delete(project)
    db.commit()
    return project

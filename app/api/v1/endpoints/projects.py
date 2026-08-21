from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_active_user, get_db
from app.core.pagination import Pagination, apply_pagination, pagination_params
from app.core.policy import policy
from app.models.project import Project, ProjectSubmission
from app.models.user import User
from app.schemas.project import (
    Project as ProjectSchema,
)
from app.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
)

router = APIRouter()


def _get_project_accession(project_submission: ProjectSubmission) -> str:
    if hasattr(project_submission, "accession"):
        return project_submission.accession


@router.get("/", response_model=List[ProjectSchema])
def read_projects(
    db: Session = Depends(get_db),
    pagination: Pagination = Depends(pagination_params),
    taxon_id: Optional[int] = Query(None, description="Filter by organism taxon ID"),
    project_type: Optional[str] = Query(None, description="Filter by project type"),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Retrieve projects.
    """
    # All users can read projects
    query = db.query(Project)
    if taxon_id:
        query = query.filter(Project.taxon_id == taxon_id)
   if project_type:
        query = query.filter(Project.project_type == project_type)

    projects = apply_pagination(query, pagination).all()
    if not projects:
        raise HTTPException(status_code=404, detail="Projects not found")
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
    project = Project(**project_in.model_dump(exclude_none=True))
    db.add(project)
    db.flush()  # Ensure project IDs
    try:
        prepared_payload = {
            "taxon_id": project.taxon_id,
            "project_type": project.project_type,
            "study_type": project.study_type,
            "alias": project.alias,
            "title": project.title,
            "description": project.description,
            "centre_name": project.centre_name,
            "study_attributes": project.study_attributes,
        }
        db.add(ProjectSubmission(project_id=project.id, prepared_payload=prepared_payload))
    except Exception:
        db.rollback()
        raise
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

    # If no project accession in the project table, injects accession from project_submission table into the endpoint response (does not change db content)
    if not project.project_accession:
        project_submission = (
            db.query(ProjectSubmission).filter(ProjectSubmission.project_id == project_id).first()
        )
        if not project_submission:
            raise HTTPException(status_code=404, detail="Project submission record not found")
        else:
            accession = _get_project_accession(project_submission)
            project.project_accession = accession

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

    update_data = project_in.model_dump(exclude_unset=True)
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

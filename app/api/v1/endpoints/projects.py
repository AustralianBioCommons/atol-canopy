from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import (
    get_current_active_user,
    get_current_superuser,
    get_db,
    require_role,
)
from app.models.project import Project, ProjectExperiment
from app.models.user import User
from app.schemas.project import (
    Project as ProjectSchema,
    ProjectCreate,
    ProjectExperiment as ProjectExperimentSchema,
    ProjectExperimentCreate,
    ProjectUpdate,
)

router = APIRouter()


@router.get("/", response_model=List[ProjectSchema])
def read_projects(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Retrieve projects.
    """
    # All users can read projects
    projects = db.query(Project).offset(skip).limit(limit).all()
    return projects


@router.post("/", response_model=ProjectSchema)
def create_project(
    *,
    db: Session = Depends(get_db),
    project_in: ProjectCreate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Create new project.
    """
    # Only users with 'curator' or 'admin' role can create projects
    require_role(current_user, ["curator", "admin"])
    
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
    # Only users with 'curator' or 'admin' role can update projects
    require_role(current_user, ["curator", "admin"])
    
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
def delete_project(
    *,
    db: Session = Depends(get_db),
    project_id: UUID,
    current_user: User = Depends(get_current_superuser),
) -> Any:
    """
    Delete a project.
    """
    # Only superusers can delete projects
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    db.delete(project)
    db.commit()
    return project


# Project Experiment endpoints
@router.get("/experiments/", response_model=List[ProjectExperimentSchema])
def read_project_experiments(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    project_id: Optional[UUID] = Query(None, description="Filter by project ID"),
    experiment_id: Optional[UUID] = Query(None, description="Filter by experiment ID"),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Retrieve project-experiment relationships.
    """
    # All users can read project-experiment relationships
    query = db.query(ProjectExperiment)
    if project_id:
        query = query.filter(ProjectExperiment.project_id == project_id)
    if experiment_id:
        query = query.filter(ProjectExperiment.experiment_id == experiment_id)
    
    relationships = query.offset(skip).limit(limit).all()
    return relationships


@router.post("/experiments/", response_model=ProjectExperimentSchema)
def create_project_experiment(
    *,
    db: Session = Depends(get_db),
    relationship_in: ProjectExperimentCreate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Create new project-experiment relationship.
    """
    # Only users with 'curator' or 'admin' role can create project-experiment relationships
    require_role(current_user, ["curator", "admin"])
    
    relationship = ProjectExperiment(
        project_id=relationship_in.project_id,
        experiment_id=relationship_in.experiment_id,
        project_accession=relationship_in.project_accession,
        experiment_accession=relationship_in.experiment_accession,
    )
    db.add(relationship)
    db.commit()
    db.refresh(relationship)
    return relationship


@router.delete("/experiments/{relationship_id}", response_model=ProjectExperimentSchema)
def delete_project_experiment(
    *,
    db: Session = Depends(get_db),
    relationship_id: UUID,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Delete a project-experiment relationship.
    """
    # Only users with 'curator' or 'admin' role can delete project-experiment relationships
    require_role(current_user, ["curator", "admin"])
    
    relationship = db.query(ProjectExperiment).filter(ProjectExperiment.id == relationship_id).first()
    if not relationship:
        raise HTTPException(status_code=404, detail="Project-experiment relationship not found")
    
    db.delete(relationship)
    db.commit()
    return relationship

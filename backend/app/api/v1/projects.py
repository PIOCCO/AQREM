from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_tenant_context, require_role
from app.core.roles import Role
from app.core.tenant import TenantContext
from app.db.session import get_db
from app.models.project import Project
from app.schemas.organization import ProjectCreate, ProjectResponse

router = APIRouter()


@router.get("", response_model=list[ProjectResponse])
def list_projects(
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> list[Project]:
    return db.query(Project).filter(Project.organization_id == tenant.organization_id).all()


@router.post("", response_model=ProjectResponse)
def create_project(
    payload: ProjectCreate,
    tenant: TenantContext = Depends(require_role(Role.EDITOR)),
    db: Session = Depends(get_db),
) -> Project:
    project = Project(
        organization_id=tenant.organization_id,
        name=payload.name,
        description=payload.description,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> Project:
    project = db.get(Project, project_id)
    if project is None or project.organization_id != tenant.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project

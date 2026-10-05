from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.dependencies import get_tenant_context, require_role
from app.core.roles import Role
from app.core.tenant import TenantContext
from app.db.session import get_db
from app.models.enums import AnswerStatus
from app.models.evidence import EvidenceItem
from app.models.project import Project
from app.models.questionnaire import Answer, Question, Questionnaire
from app.models.source import Source
from app.schemas.organization import ProjectCreate, ProjectResponse, ProjectSummaryResponse

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


@router.get("/summaries", response_model=list[ProjectSummaryResponse])
def list_project_summaries(
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> list[ProjectSummaryResponse]:
    projects = db.query(Project).filter(Project.organization_id == tenant.organization_id).all()
    summaries: list[ProjectSummaryResponse] = []
    for project in projects:
        questionnaires = (
            db.query(func.count(Questionnaire.id))
            .filter(Questionnaire.project_id == project.id)
            .scalar()
            or 0
        )
        sources = (
            db.query(func.count(Source.id)).filter(Source.project_id == project.id).scalar() or 0
        )
        pending = (
            db.query(func.count(Answer.id))
            .join(Question, Question.id == Answer.question_id)
            .join(Questionnaire, Questionnaire.id == Question.questionnaire_id)
            .filter(
                Questionnaire.project_id == project.id,
                Answer.status == AnswerStatus.NEEDS_REVIEW.value,
            )
            .scalar()
            or 0
        )
        stale = (
            db.query(func.count(Answer.id))
            .join(Question, Question.id == Answer.question_id)
            .join(Questionnaire, Questionnaire.id == Question.questionnaire_id)
            .filter(Questionnaire.project_id == project.id, Answer.potentially_stale.is_(True))
            .scalar()
            or 0
        )
        evidence_items = (
            db.query(func.count(EvidenceItem.id))
            .filter(
                EvidenceItem.organization_id == tenant.organization_id,
                EvidenceItem.project_id == project.id,
            )
            .scalar()
            or 0
        )
        summaries.append(
            ProjectSummaryResponse(
                id=project.id,
                name=project.name,
                description=project.description,
                questionnaire_count=questionnaires,
                source_count=sources,
                evidence_item_count=evidence_items,
                pending_review_count=pending,
                potentially_stale_count=stale,
                updated_at=project.updated_at,
            )
        )
    return summaries


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

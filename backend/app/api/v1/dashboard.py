from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.dependencies import get_tenant_context
from app.core.tenant import TenantContext
from app.db.session import get_db
from app.models.enums import AnswerStatus
from app.models.evidence import EvidenceItem
from app.models.project import Project
from app.models.questionnaire import Answer, Question, Questionnaire
from app.models.source import Source

router = APIRouter()


@router.get("/metrics")
def dashboard_metrics(
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> dict:
    org_id = tenant.organization_id
    return {
        "projects": db.query(func.count(Project.id)).filter(Project.organization_id == org_id).scalar() or 0,
        "sources": db.query(func.count(Source.id)).filter(Source.organization_id == org_id).scalar() or 0,
        "evidence_items": db.query(func.count(EvidenceItem.id))
        .filter(EvidenceItem.organization_id == org_id)
        .scalar()
        or 0,
        "questionnaires": db.query(func.count(Questionnaire.id))
        .filter(Questionnaire.organization_id == org_id)
        .scalar()
        or 0,
        "questions": db.query(func.count(Question.id)).filter(Question.organization_id == org_id).scalar() or 0,
        "approved_answers": db.query(func.count(Answer.id))
        .filter(Answer.organization_id == org_id, Answer.status == AnswerStatus.APPROVED.value)
        .scalar()
        or 0,
        "pending_review": db.query(func.count(Answer.id))
        .filter(Answer.organization_id == org_id, Answer.status == AnswerStatus.NEEDS_REVIEW.value)
        .scalar()
        or 0,
        "insufficient_evidence": db.query(func.count(Answer.id))
        .filter(Answer.organization_id == org_id, Answer.evidence_sufficiency == "insufficient")
        .scalar()
        or 0,
        "potentially_stale": db.query(func.count(Answer.id))
        .filter(Answer.organization_id == org_id, Answer.potentially_stale.is_(True))
        .scalar()
        or 0,
    }

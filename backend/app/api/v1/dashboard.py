from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.dependencies import get_tenant_context
from app.core.tenant import TenantContext
from app.db.session import get_db
from app.models.enums import AnswerStatus, SourceStatus
from app.models.evidence import EvidenceItem
from app.models.project import Project
from app.models.questionnaire import Answer, Question, Questionnaire
from app.models.source import Source

router = APIRouter()


def _metrics_for_org(db: Session, org_id: UUID, project_id: UUID | None = None) -> dict:
    q_filter = Question.organization_id == org_id
    a_filter = Answer.organization_id == org_id
    qn_filter = Questionnaire.organization_id == org_id
    src_filter = Source.organization_id == org_id
    ev_filter = EvidenceItem.organization_id == org_id
    if project_id:
        q_filter = q_filter & (Question.questionnaire_id.in_(
            db.query(Questionnaire.id).filter(
                Questionnaire.organization_id == org_id, Questionnaire.project_id == project_id
            )
        ))
        qn_filter = qn_filter & (Questionnaire.project_id == project_id)
        src_filter = src_filter & (Source.project_id == project_id)
        ev_filter = ev_filter & (
            (EvidenceItem.project_id == project_id) | (EvidenceItem.project_id.is_(None))
        )
        a_filter = a_filter & (
            Answer.question_id.in_(
                db.query(Question.id).filter(
                    Question.organization_id == org_id,
                    Question.questionnaire_id.in_(
                        db.query(Questionnaire.id).filter(
                            Questionnaire.organization_id == org_id,
                            Questionnaire.project_id == project_id,
                        )
                    ),
                )
            )
        )

    return {
        "projects": db.query(func.count(Project.id)).filter(Project.organization_id == org_id).scalar() or 0,
        "sources": db.query(func.count(Source.id)).filter(src_filter).scalar() or 0,
        "evidence_items": db.query(func.count(EvidenceItem.id)).filter(ev_filter).scalar() or 0,
        "questionnaires": db.query(func.count(Questionnaire.id)).filter(qn_filter).scalar() or 0,
        "questions": db.query(func.count(Question.id)).filter(q_filter).scalar() or 0,
        "approved_answers": db.query(func.count(Answer.id))
        .filter(a_filter, Answer.status == AnswerStatus.APPROVED.value)
        .scalar()
        or 0,
        "pending_review": db.query(func.count(Answer.id))
        .filter(a_filter, Answer.status == AnswerStatus.NEEDS_REVIEW.value)
        .scalar()
        or 0,
        "insufficient_evidence": db.query(func.count(Answer.id))
        .filter(a_filter, Answer.evidence_sufficiency == "insufficient")
        .scalar()
        or 0,
        "potentially_stale": db.query(func.count(Answer.id))
        .filter(a_filter, Answer.potentially_stale.is_(True))
        .scalar()
        or 0,
        "sources_indexing": db.query(func.count(Source.id))
        .filter(src_filter, Source.status == SourceStatus.INDEXING.value)
        .scalar()
        or 0,
    }


@router.get("/metrics")
def dashboard_metrics(
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
    project_id: UUID | None = Query(default=None),
) -> dict:
    return _metrics_for_org(db, tenant.organization_id, project_id)


@router.get("/overview")
def dashboard_overview(
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
    project_id: UUID | None = Query(default=None),
) -> dict:
    metrics = _metrics_for_org(db, tenant.organization_id, project_id)
    qn_query = db.query(Questionnaire).filter(Questionnaire.organization_id == tenant.organization_id)
    if project_id:
        qn_query = qn_query.filter(Questionnaire.project_id == project_id)
    questionnaires = qn_query.order_by(Questionnaire.updated_at.desc()).limit(8).all()

    recent: list[dict] = []
    for qn in questionnaires:
        total_q = (
            db.query(func.count(Question.id)).filter(Question.questionnaire_id == qn.id).scalar() or 0
        )
        approved = (
            db.query(func.count(Answer.id))
            .join(Question, Question.id == Answer.question_id)
            .filter(Question.questionnaire_id == qn.id, Answer.status == AnswerStatus.APPROVED.value)
            .scalar()
            or 0
        )
        pct = int(round((approved / total_q) * 100)) if total_q else 0
        recent.append(
            {
                "id": str(qn.id),
                "name": qn.name,
                "status": qn.status,
                "question_count": total_q,
                "approved_count": approved,
                "progress_percent": pct,
            }
        )

    project_name = None
    if project_id:
        project = db.get(Project, project_id)
        if project and project.organization_id == tenant.organization_id:
            project_name = project.name

    return {
        "metrics": metrics,
        "project_id": str(project_id) if project_id else None,
        "project_name": project_name,
        "recent_questionnaires": recent,
    }

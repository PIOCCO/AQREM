from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from app.core.dependencies import get_tenant_context
from app.core.tenant import TenantContext
from app.db.session import get_db
from app.models.enums import AnswerStatus
from app.models.project import Project
from app.models.questionnaire import Answer, Question, Questionnaire
from app.schemas.review import ReviewQueueItem, ReviewQueueResponse

router = APIRouter()


def _review_reason(answer: Answer) -> str:
    if answer.potentially_stale:
        return "Evidence changed"
    if answer.evidence_sufficiency == "insufficient":
        return "Insufficient evidence"
    if answer.confidence in {"low", "medium"}:
        return "Low confidence"
    if answer.generation_source == "stale_regeneration":
        return "Evidence changed"
    return "New AI answer"


@router.get("", response_model=ReviewQueueResponse)
def list_review_queue(
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
    project_id: UUID | None = Query(default=None),
    search: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> ReviewQueueResponse:
    query = (
        db.query(Answer)
        .join(Question, Question.id == Answer.question_id)
        .join(Questionnaire, Questionnaire.id == Question.questionnaire_id)
        .filter(
            Answer.organization_id == tenant.organization_id,
            Answer.status == AnswerStatus.NEEDS_REVIEW.value,
        )
    )
    if project_id:
        query = query.filter(Questionnaire.project_id == project_id)
    if search:
        query = query.filter(
            Question.text.ilike(f"%{search}%") | Question.external_id.ilike(f"%{search}%")
        )

    total = query.count()
    answers = (
        query.options(
            joinedload(Answer.question).joinedload(Question.questionnaire),
        )
        .order_by(Answer.updated_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    items: list[ReviewQueueItem] = []
    for answer in answers:
        question = answer.question
        questionnaire = question.questionnaire if question else None
        project_name = None
        if questionnaire and questionnaire.project_id:
            project = db.get(Project, questionnaire.project_id)
            project_name = project.name if project else None
        items.append(
            ReviewQueueItem(
                answer_id=answer.id,
                question_id=question.id if question else answer.question_id,
                question_external_id=question.external_id if question else "",
                question_text=question.text if question else "",
                questionnaire_id=questionnaire.id if questionnaire else None,
                questionnaire_name=questionnaire.name if questionnaire else None,
                project_id=questionnaire.project_id if questionnaire else None,
                project_name=project_name,
                status=answer.status,
                confidence=answer.confidence,
                evidence_sufficiency=answer.evidence_sufficiency,
                potentially_stale=answer.potentially_stale,
                reason=_review_reason(answer),
            )
        )
    return ReviewQueueResponse(items=items, total=total, offset=offset, limit=limit)

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_tenant_context, require_role
from app.core.roles import Role
from app.core.tenant import TenantContext
from app.db.session import get_db
from app.models.questionnaire import Answer, Question
from app.models.staleness import AnswerStalenessEvent
from app.models.enums import StalenessEventStatus
from app.schemas.questionnaire import AnswerResponse
from app.schemas.staleness import (
    RevalidateResponse,
    StaleAnswerDetailResponse,
    StaleAnswerListResponse,
    StaleAnswerSummary,
    ChangedEvidenceItem,
)
from app.services.answering.service import AnsweringService
from app.services.staleness.service import StalenessService
from app.api.v1.questionnaires import _build_answer_response

router = APIRouter()


@router.get("", response_model=StaleAnswerListResponse)
def list_stale_answers(
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
    project_id: UUID | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> StaleAnswerListResponse:
    service = StalenessService(db)
    rows, total = service.list_stale_answers(
        organization_id=tenant.organization_id,
        project_id=project_id,
        status=status_filter,
        search=search,
        offset=offset,
        limit=limit,
    )
    items: list[StaleAnswerSummary] = []
    for answer in rows:
        question = answer.question
        questionnaire = question.questionnaire if question else None
        project = None
        project_name = None
        if questionnaire and questionnaire.project_id:
            from app.models.project import Project

            project = db.get(Project, questionnaire.project_id)
            project_name = project.name if project else None
        open_count = (
            db.query(AnswerStalenessEvent)
            .filter(
                AnswerStalenessEvent.answer_id == answer.id,
                AnswerStalenessEvent.status == StalenessEventStatus.OPEN.value,
            )
            .count()
        )
        items.append(
            StaleAnswerSummary(
                answer_id=answer.id,
                question_id=question.id if question else answer.question_id,
                question_external_id=question.external_id if question else "",
                question_text=question.text if question else "",
                project_id=questionnaire.project_id if questionnaire else None,
                project_name=project_name,
                status=answer.status,
                potentially_stale=answer.potentially_stale,
                stale_detected_at=answer.stale_detected_at,
                stale_reason=answer.stale_reason,
                approved_text=answer.approved_text,
                draft_text=answer.draft_text,
                changed_evidence_count=open_count,
            )
        )
    return StaleAnswerListResponse(items=items, total=total, offset=offset, limit=limit)


@router.get("/{answer_id}", response_model=StaleAnswerDetailResponse)
def get_stale_answer(
    answer_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> StaleAnswerDetailResponse:
    detail = StalenessService(db).get_stale_answer_detail(
        organization_id=tenant.organization_id, answer_id=answer_id
    )
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stale answer not found")
    answer: Answer = detail["answer"]
    question = detail["question"]
    project = detail["project"]
    questionnaire = detail["questionnaire"]
    return StaleAnswerDetailResponse(
        answer_id=answer.id,
        question_id=question.id,
        question_external_id=question.external_id,
        question_text=question.text,
        project_id=project.id if project else None,
        project_name=project.name if project else None,
        questionnaire_id=questionnaire.id,
        questionnaire_name=questionnaire.name,
        status=answer.status,
        potentially_stale=answer.potentially_stale,
        stale_reason=answer.stale_reason,
        approved_text=answer.approved_text,
        draft_text=answer.draft_text,
        generation_source=answer.generation_source,
        changed_evidence=[ChangedEvidenceItem(**item) for item in detail["changed_evidence"]],
        library_entry_status=detail["library_entry_status"],
    )


@router.post("/{answer_id}/revalidate", response_model=RevalidateResponse)
def revalidate_stale_answer(
    answer_id: UUID,
    tenant: TenantContext = Depends(require_role(Role.REVIEWER)),
    db: Session = Depends(get_db),
) -> RevalidateResponse:
    try:
        result = StalenessService(db).revalidate(
            organization_id=tenant.organization_id,
            answer_id=answer_id,
            user_id=tenant.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    db.commit()
    return RevalidateResponse(**result)


@router.post("/{answer_id}/regenerate", response_model=AnswerResponse)
async def regenerate_stale_answer(
    answer_id: UUID,
    tenant: TenantContext = Depends(require_role(Role.EDITOR)),
    db: Session = Depends(get_db),
) -> AnswerResponse:
    answer = db.get(Answer, answer_id)
    if answer is None or answer.organization_id != tenant.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Answer not found")
    question = (
        db.query(Question)
        .filter(Question.id == answer.question_id, Question.organization_id == tenant.organization_id)
        .first()
    )
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    regenerated = await AnsweringService(db).generate_for_question(
        question=question,
        user_id=tenant.user_id,
        skip_library_reuse=True,
        stale_regeneration=True,
    )
    db.commit()
    return _build_answer_response(db, regenerated)

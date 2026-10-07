from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.audit.service import record_audit
from app.core.config import get_settings
from app.core.dependencies import get_tenant_context, require_role
from app.core.rate_limit import LLM_GENERATE_LIMIT, limiter
from app.core.roles import Role
from app.core.tenant import TenantContext
from app.db.session import get_db
from app.models.evidence import EvidenceItem
from app.models.project import Project
from app.models.questionnaire import Answer, AnswerEvidenceLink, Question, Questionnaire
from app.schemas.questionnaire import (
    AnswerEditRequest,
    AnswerResponse,
    EvidenceCitation,
    GenerateBatchResponse,
    QuestionDetailResponse,
    QuestionnaireCreate,
    QuestionnaireResponse,
    QuestionResponse,
    QuestionAnswerSummary,
    QuestionWithAnswerResponse,
)
from app.services.answering.service import AnsweringService
from app.services.questionnaire.export import build_export_rows, render_csv_bytes, render_xlsx_bytes
from app.services.questionnaire.extract import extract_questionnaire_bytes
from app.services.questionnaire.normalize import normalize_question
from app.services.storage.factory import get_blob_storage

router = APIRouter()


def _questionnaire_response(db: Session, questionnaire: Questionnaire) -> QuestionnaireResponse:
    count = db.query(func.count(Question.id)).filter(Question.questionnaire_id == questionnaire.id).scalar() or 0
    return QuestionnaireResponse(
        id=questionnaire.id,
        organization_id=questionnaire.organization_id,
        project_id=questionnaire.project_id,
        name=questionnaire.name,
        recipient=questionnaire.recipient,
        description=questionnaire.description,
        status=questionnaire.status,
        question_count=count,
        created_at=questionnaire.created_at,
    )


def _build_answer_response(db: Session, answer: Answer | None) -> AnswerResponse | None:
    if answer is None:
        return None
    links = db.query(AnswerEvidenceLink).filter(AnswerEvidenceLink.answer_id == answer.id).all()
    evidence: list[EvidenceCitation] = []
    for link in links:
        item = db.get(EvidenceItem, link.evidence_item_id)
        if item is None:
            continue
        evidence.append(
            EvidenceCitation(
                id=item.id,
                file_name=item.file_name,
                file_path=item.file_path,
                line_start=item.line_start,
                line_end=item.line_end,
                repository=item.repository,
                commit_hash=item.commit_hash,
                evidence_strength=link.evidence_strength or item.evidence_strength,
                content_preview=item.content[:400],
            )
        )
    return AnswerResponse(
        id=answer.id,
        question_id=answer.question_id,
        draft_text=answer.draft_text,
        approved_text=answer.approved_text,
        confidence=answer.confidence,
        evidence_sufficiency=answer.evidence_sufficiency,
        reasoning_summary=answer.reasoning_summary,
        status=answer.status,
        version=answer.version,
        potentially_stale=answer.potentially_stale,
        generation_source=answer.generation_source,
        library_entry_id=answer.library_entry_id,
        stale_detected_at=answer.stale_detected_at,
        stale_reason=answer.stale_reason,
        evidence=evidence,
    )


def _get_questionnaire(db: Session, tenant: TenantContext, questionnaire_id: UUID) -> Questionnaire:
    questionnaire = db.get(Questionnaire, questionnaire_id)
    if questionnaire is None or questionnaire.organization_id != tenant.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Questionnaire not found")
    return questionnaire


def _get_question(db: Session, tenant: TenantContext, question_id: UUID) -> Question:
    question = (
        db.query(Question)
        .options(joinedload(Question.answer))
        .filter(Question.id == question_id, Question.organization_id == tenant.organization_id)
        .first()
    )
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    return question


@router.get("", response_model=list[QuestionnaireResponse])
def list_questionnaires(
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
    project_id: UUID | None = Query(default=None),
) -> list[QuestionnaireResponse]:
    query = db.query(Questionnaire).filter(Questionnaire.organization_id == tenant.organization_id)
    if project_id:
        query = query.filter(Questionnaire.project_id == project_id)
    rows = query.order_by(Questionnaire.created_at.desc()).all()
    return [_questionnaire_response(db, row) for row in rows]


@router.post("", response_model=QuestionnaireResponse)
def create_questionnaire(
    payload: QuestionnaireCreate,
    tenant: TenantContext = Depends(require_role(Role.EDITOR)),
    db: Session = Depends(get_db),
) -> QuestionnaireResponse:
    if payload.project_id:
        project = db.get(Project, payload.project_id)
        if project is None or project.organization_id != tenant.organization_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid project")
    questionnaire = Questionnaire(
        organization_id=tenant.organization_id,
        project_id=payload.project_id,
        name=payload.name,
        recipient=payload.recipient,
        description=payload.description,
    )
    db.add(questionnaire)
    db.commit()
    db.refresh(questionnaire)
    record_audit(
        db,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        action="questionnaire_created",
        resource_type="questionnaire",
        resource_id=str(questionnaire.id),
    )
    db.commit()
    return _questionnaire_response(db, questionnaire)


@router.get("/{questionnaire_id}", response_model=QuestionnaireResponse)
def get_questionnaire(
    questionnaire_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> QuestionnaireResponse:
    return _questionnaire_response(db, _get_questionnaire(db, tenant, questionnaire_id))


@router.get("/{questionnaire_id}/questions", response_model=list[QuestionWithAnswerResponse])
def list_questions(
    questionnaire_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
    status_filter: str | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None),
) -> list[QuestionWithAnswerResponse]:
    _get_questionnaire(db, tenant, questionnaire_id)
    query = (
        db.query(Question)
        .options(joinedload(Question.answer))
        .filter(Question.questionnaire_id == questionnaire_id)
    )
    if search:
        query = query.filter(
            Question.text.ilike(f"%{search}%") | Question.external_id.ilike(f"%{search}%")
        )
    questions = query.order_by(Question.sort_order.asc(), Question.external_id.asc()).all()
    items: list[QuestionWithAnswerResponse] = []
    for question in questions:
        answer = question.answer
        if status_filter and (answer is None or answer.status != status_filter):
            continue
        summary = None
        if answer:
            strength = None
            link = (
                db.query(AnswerEvidenceLink)
                .filter(AnswerEvidenceLink.answer_id == answer.id)
                .first()
            )
            if link:
                strength = link.evidence_strength
            summary = QuestionAnswerSummary(
                status=answer.status,
                confidence=answer.confidence,
                evidence_sufficiency=answer.evidence_sufficiency,
                potentially_stale=answer.potentially_stale,
                evidence_strength=strength,
            )
        items.append(
            QuestionWithAnswerResponse(
                id=question.id,
                questionnaire_id=question.questionnaire_id,
                external_id=question.external_id,
                section=question.section,
                text=question.text,
                sort_order=question.sort_order,
                answer=summary,
            )
        )
    return items


@router.get("/{questionnaire_id}/export/csv")
def export_questionnaire_csv(
    questionnaire_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
    approved_only: bool = Query(default=False),
    needs_review_only: bool = Query(default=False),
) -> Response:
    try:
        rows = build_export_rows(
            db,
            organization_id=tenant.organization_id,
            questionnaire_id=questionnaire_id,
            approved_only=approved_only,
            needs_review_only=needs_review_only,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    questionnaire = _get_questionnaire(db, tenant, questionnaire_id)
    suffix = "approved" if approved_only else "export"
    filename = f"{questionnaire.name.replace(' ', '_')}_{suffix}.csv"
    record_audit(
        db,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        action="questionnaire_exported",
        resource_type="questionnaire",
        resource_id=str(questionnaire_id),
        metadata={"format": "csv", "rows": len(rows), "approved_only": approved_only},
    )
    db.commit()
    return Response(
        content=render_csv_bytes(rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{questionnaire_id}/export/xlsx")
def export_questionnaire_xlsx(
    questionnaire_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
    approved_only: bool = Query(default=False),
    needs_review_only: bool = Query(default=False),
) -> Response:
    try:
        rows = build_export_rows(
            db,
            organization_id=tenant.organization_id,
            questionnaire_id=questionnaire_id,
            approved_only=approved_only,
            needs_review_only=needs_review_only,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    questionnaire = _get_questionnaire(db, tenant, questionnaire_id)
    suffix = "approved" if approved_only else "export"
    filename = f"{questionnaire.name.replace(' ', '_')}_{suffix}.xlsx"
    record_audit(
        db,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        action="questionnaire_exported",
        resource_type="questionnaire",
        resource_id=str(questionnaire_id),
        metadata={"format": "xlsx", "rows": len(rows), "approved_only": approved_only},
    )
    db.commit()
    return Response(
        content=render_xlsx_bytes(rows),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{questionnaire_id}/upload")
async def upload_questionnaire(
    questionnaire_id: UUID,
    file: UploadFile = File(...),
    tenant: TenantContext = Depends(require_role(Role.EDITOR)),
    db: Session = Depends(get_db),
) -> dict:
    settings = get_settings()
    questionnaire = _get_questionnaire(db, tenant, questionnaire_id)
    filename = file.filename or "questionnaire.csv"
    data = await file.read()
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large")

    try:
        extracted = extract_questionnaire_bytes(filename, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if not extracted:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No questions extracted")

    storage = get_blob_storage()
    blob_path = f"{tenant.organization_id}/questionnaires/{questionnaire.id}/{filename}"
    storage.upload_bytes(blob_path, data, file.content_type or "application/octet-stream")

    db.query(Question).filter(Question.questionnaire_id == questionnaire.id).delete()
    for idx, row in enumerate(extracted):
        db.add(
            Question(
                organization_id=tenant.organization_id,
                questionnaire_id=questionnaire.id,
                external_id=row.external_id,
                section=row.section,
                text=row.text,
                normalized_text=normalize_question(row.text),
                expected_answer=row.expected_answer,
                existing_answer=row.existing_answer,
                sort_order=idx,
            )
        )
    db.commit()
    record_audit(
        db,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        action="questionnaire_uploaded",
        resource_type="questionnaire",
        resource_id=str(questionnaire.id),
        metadata={"questions": len(extracted), "filename": filename},
    )
    db.commit()
    return {"questionnaire_id": str(questionnaire.id), "questions_extracted": len(extracted)}


@router.post("/{questionnaire_id}/generate", response_model=GenerateBatchResponse)
@limiter.limit(LLM_GENERATE_LIMIT)
async def generate_all_answers(
    request: Request,
    questionnaire_id: UUID,
    tenant: TenantContext = Depends(require_role(Role.EDITOR)),
    db: Session = Depends(get_db),
) -> GenerateBatchResponse:
    _get_questionnaire(db, tenant, questionnaire_id)
    questions = (
        db.query(Question)
        .options(joinedload(Question.answer))
        .filter(Question.questionnaire_id == questionnaire_id)
        .order_by(Question.sort_order.asc())
        .all()
    )
    service = AnsweringService(db)
    generated = 0
    insufficient = 0
    for question in questions:
        answer = await service.generate_for_question(question=question, user_id=tenant.user_id)
        generated += 1
        if answer.evidence_sufficiency == "insufficient":
            insufficient += 1
    db.commit()
    return GenerateBatchResponse(
        questionnaire_id=questionnaire_id,
        generated=generated,
        insufficient=insufficient,
    )


@router.get("/questions/{question_id}", response_model=QuestionDetailResponse)
def get_question_detail(
    question_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> QuestionDetailResponse:
    question = _get_question(db, tenant, question_id)
    return QuestionDetailResponse(
        question=QuestionResponse.model_validate(question),
        answer=_build_answer_response(db, question.answer),
    )


@router.post("/questions/{question_id}/generate", response_model=AnswerResponse)
@limiter.limit(LLM_GENERATE_LIMIT)
async def generate_question_answer(
    request: Request,
    question_id: UUID,
    tenant: TenantContext = Depends(require_role(Role.EDITOR)),
    db: Session = Depends(get_db),
) -> AnswerResponse:
    question = _get_question(db, tenant, question_id)
    answer = await AnsweringService(db).generate_for_question(
        question=question, user_id=tenant.user_id
    )
    db.commit()
    return _build_answer_response(db, answer)


@router.post("/answers/{answer_id}/approve", response_model=AnswerResponse)
async def approve_answer(
    answer_id: UUID,
    tenant: TenantContext = Depends(require_role(Role.REVIEWER)),
    db: Session = Depends(get_db),
) -> AnswerResponse:
    answer = db.get(Answer, answer_id)
    if answer is None or answer.organization_id != tenant.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Answer not found")
    await AnsweringService(db).approve_answer(answer, tenant.user_id)
    db.commit()
    return _build_answer_response(db, answer)


@router.post("/answers/{answer_id}/edit", response_model=AnswerResponse)
async def edit_answer(
    answer_id: UUID,
    payload: AnswerEditRequest,
    tenant: TenantContext = Depends(require_role(Role.REVIEWER)),
    db: Session = Depends(get_db),
) -> AnswerResponse:
    answer = db.get(Answer, answer_id)
    if answer is None or answer.organization_id != tenant.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Answer not found")
    await AnsweringService(db).edit_answer(answer, tenant.user_id, payload.text)
    db.commit()
    return _build_answer_response(db, answer)


@router.post("/answers/{answer_id}/reject", response_model=AnswerResponse)
def reject_answer(
    answer_id: UUID,
    tenant: TenantContext = Depends(require_role(Role.REVIEWER)),
    db: Session = Depends(get_db),
) -> AnswerResponse:
    answer = db.get(Answer, answer_id)
    if answer is None or answer.organization_id != tenant.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Answer not found")
    AnsweringService(db).reject_answer(answer, tenant.user_id)
    db.commit()
    return _build_answer_response(db, answer)


@router.post("/questions/{question_id}/regenerate", response_model=AnswerResponse)
@limiter.limit(LLM_GENERATE_LIMIT)
async def regenerate_answer(
    request: Request,
    question_id: UUID,
    tenant: TenantContext = Depends(require_role(Role.EDITOR)),
    db: Session = Depends(get_db),
) -> AnswerResponse:
    question = _get_question(db, tenant, question_id)
    answer = await AnsweringService(db).generate_for_question(
        question=question, user_id=tenant.user_id
    )
    db.commit()
    return _build_answer_response(db, answer)

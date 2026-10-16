"""Shared retrieval + LLM + behavior classification for chat and questionnaires."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.enums import AnswerOutcome
from app.models.evidence import EvidenceItem
from app.services.llm.guardrails import sanitize_evidence_content
from app.services.llm.base import AnswerRequest, StructuredAnswer
from app.services.llm.errors import ASSISTANT_UNAVAILABLE_MESSAGE, ModelServiceError
from app.services.llm.factory import get_llm_provider
from app.services.llm.guardrails import (
    clamp_question,
    validate_structured_answer,
    wrap_evidence_for_prompt,
)
from app.services.rag.behavior import (
    BehaviorResult,
    classify_behavior,
    classify_early_behavior,
    compose_employee_answer,
)
from app.services.access_control.context import UserAccessContext
from app.services.chat.messages import format_empty_retrieval_message
from app.services.retrieval.scope import count_org_evidence_chunks
from app.services.retrieval.debug_log import log_rag_event
from app.services.retrieval.service import RetrievalService

logger = logging.getLogger("aqrem.rag")


def evidence_page(item) -> int | None:
    meta = getattr(item, "item_metadata", None) or {}
    page = meta.get("page") if isinstance(meta, dict) else None
    try:
        return int(page) if page is not None else None
    except (TypeError, ValueError):
        return None


def source_reference(item) -> str:
    name = getattr(item, "file_name", None) or getattr(item, "file_path", None) or "document"
    page = evidence_page(item)
    return f"{name}, p. {page}" if page else name


def append_source_references(answer: str, items: list, selected_ids: set) -> str:
    """Guarantee every grounded answer ends with document name (+ page) references."""
    refs: list[str] = []
    for item in items:
        if item.id in selected_ids:
            ref = source_reference(item)
            if ref not in refs:
                refs.append(ref)
    if not refs or not (answer or "").strip():
        return answer
    if "\nSources:" in answer:
        return answer
    return answer.rstrip() + "\n\nSources: " + "; ".join(refs)


def evidence_blocks(items: list[EvidenceItem]) -> list[dict]:
    blocks: list[dict] = []
    for item in items:
        blocks.append(
            {
                "id": str(item.id),
                "document": getattr(item, "file_name", None),
                "page": evidence_page(item),
                "file_path": item.file_path,
                "line_start": item.line_start,
                "line_end": item.line_end,
                "repository": item.repository,
                "commit_hash": item.commit_hash,
                "content": sanitize_evidence_content(item.content),
                "evidence_strength": item.evidence_strength,
            }
        )
    return blocks


def outcome_skips_llm(behavior: BehaviorResult) -> bool:
    return behavior.outcome in {
        AnswerOutcome.ACTION_NOT_SUPPORTED,
        AnswerOutcome.ACCESS_DENIED,
        AnswerOutcome.CLARIFICATION_REQUIRED,
        AnswerOutcome.SOURCE_UNAVAILABLE,
    }


def align_structured_with_behavior(
    structured: StructuredAnswer,
    behavior: BehaviorResult,
) -> StructuredAnswer:
    sufficiency = structured.evidence_sufficiency
    if behavior.outcome in {
        AnswerOutcome.INSUFFICIENT_EVIDENCE,
        AnswerOutcome.CONFLICTING_EVIDENCE,
    }:
        sufficiency = "insufficient"
    elif behavior.outcome == AnswerOutcome.PARTIALLY_ANSWERED:
        sufficiency = "sufficient"
    confidence = structured.confidence
    if behavior.outcome == AnswerOutcome.CONFLICTING_EVIDENCE:
        confidence = "low"
    return StructuredAnswer(
        answer=structured.answer,
        confidence=confidence,
        evidence_ids=structured.evidence_ids,
        reasoning_summary=structured.reasoning_summary,
        evidence_sufficiency=sufficiency,
    )


def selected_evidence_ids(
    structured: StructuredAnswer,
    items: list,
    behavior: BehaviorResult,
) -> set[UUID]:
    if behavior.outcome in {
        AnswerOutcome.ACCESS_DENIED,
        AnswerOutcome.SOURCE_UNAVAILABLE,
    }:
        return set()

    if behavior.outcome == AnswerOutcome.INSUFFICIENT_EVIDENCE:
        if not items:
            return set()
        return {item.id for item in items[:3]}

    selected_ids = {UUID(x) for x in structured.evidence_ids if x}
    if not selected_ids and items and structured.evidence_sufficiency != "insufficient":
        selected_ids = {item.id for item in items[:3]}
    if behavior.outcome == AnswerOutcome.CONFLICTING_EVIDENCE and items:
        selected_ids = {item.id for item in items[:6]}
    return selected_ids


@dataclass
class GroundedAnswer:
    question: str
    structured: StructuredAnswer
    behavior: BehaviorResult
    evidence_items: list
    selected_ids: set[UUID]
    composed_answer: str
    retrieval_error: str | None = None


async def generate_grounded_answer(
    db: Session,
    *,
    organization_id: UUID,
    question: str,
    project_id: UUID | None,
    limit: int | None = None,
    access: UserAccessContext | None = None,
) -> GroundedAnswer:
    safe_query = clamp_question(question)
    settings = get_settings()
    top_k = min(limit or 8, settings.llm_max_retrieval_results)

    retrieval_error: str | None = None
    items: list = []
    try:
        items = await RetrievalService(db).retrieve(
            organization_id=organization_id,
            query=safe_query,
            project_id=project_id,
            limit=top_k,
            access=access,
        )
        items = [i for i in items if i.organization_id == organization_id]
    except ModelServiceError as exc:
        logger.error(
            "Query embedding failed org=%s code=%s: %s", organization_id, exc.code, exc.admin_message
        )
        structured = StructuredAnswer(
            answer=ASSISTANT_UNAVAILABLE_MESSAGE,
            confidence="low",
            evidence_ids=[],
            reasoning_summary="Model request failed.",
            evidence_sufficiency="insufficient",
        )
        behavior = classify_behavior(
            question=safe_query, evidence_items=[], llm_sufficiency="insufficient", retrieval_error=exc.code
        )
        return GroundedAnswer(
            question=safe_query,
            structured=structured,
            behavior=behavior,
            evidence_items=[],
            selected_ids=set(),
            composed_answer=ASSISTANT_UNAVAILABLE_MESSAGE,
            retrieval_error=exc.code,
        )
    except Exception:
        logger.exception("Retrieval failed org=%s", organization_id)
        retrieval_error = "retrieval_failed"

    pre_behavior = classify_early_behavior(question=safe_query, retrieval_error=retrieval_error)
    if pre_behavior and outcome_skips_llm(pre_behavior):
        structured = StructuredAnswer(
            answer="",
            confidence="low",
            evidence_ids=[],
            reasoning_summary=None,
            evidence_sufficiency="insufficient",
        )
        return GroundedAnswer(
            question=safe_query,
            structured=structured,
            behavior=pre_behavior,
            evidence_items=[],
            selected_ids=set(),
            composed_answer=compose_employee_answer("", pre_behavior),
            retrieval_error=retrieval_error,
        )

    if not items:
        org_chunks = count_org_evidence_chunks(
            db, organization_id=organization_id, project_id=project_id
        )
        base = format_empty_retrieval_message(org_chunk_count=org_chunks)
        log_rag_event(
            "grounded_empty_retrieval",
            organization_id=organization_id,
            project_id=project_id,
            org_chunk_count=org_chunks,
            answer=base,
        )
        empty_behavior = classify_behavior(
            question=safe_query,
            evidence_items=[],
            llm_sufficiency="insufficient",
            retrieval_error=None,
        )
        structured = StructuredAnswer(
            answer=base,
            confidence="low",
            evidence_ids=[],
            reasoning_summary="No evidence items matched the query in the current scope.",
            evidence_sufficiency="insufficient",
        )
        return GroundedAnswer(
            question=safe_query,
            structured=structured,
            behavior=empty_behavior,
            evidence_items=[],
            selected_ids=set(),
            composed_answer=compose_employee_answer(base, empty_behavior),
            retrieval_error=retrieval_error,
        )

    blocks = wrap_evidence_for_prompt(evidence_blocks(items))
    log_rag_event(
        "grounded_llm_context",
        organization_id=organization_id,
        project_id=project_id,
        context_chunk_count=len(blocks),
        context_files=[getattr(i, "file_name", "") for i in items[:5]],
    )
    allowed_ids = {str(i.id) for i in items}
    llm = get_llm_provider(organization_id)
    try:
        structured = await llm.generate_answer(
            AnswerRequest(question=safe_query, evidence_blocks=blocks),
        )
    except ModelServiceError as exc:
        logger.error(
            "Answer generation failed org=%s code=%s: %s", organization_id, exc.code, exc.admin_message
        )
        structured = StructuredAnswer(
            answer=exc.user_message,
            confidence="low",
            evidence_ids=[],
            reasoning_summary="Model request failed.",
            evidence_sufficiency="insufficient",
        )
        behavior = classify_behavior(
            question=safe_query,
            evidence_items=items,
            llm_sufficiency="insufficient",
            retrieval_error=exc.code,
        )
        return GroundedAnswer(
            question=safe_query,
            structured=structured,
            behavior=behavior,
            evidence_items=items,
            selected_ids=set(),
            composed_answer=exc.user_message,
            retrieval_error=exc.code,
        )
    structured = validate_structured_answer(structured, allowed_evidence_ids=allowed_ids)

    behavior = classify_behavior(
        question=safe_query,
        evidence_items=items,
        llm_sufficiency=structured.evidence_sufficiency,
        retrieval_error=None,
    )

    if behavior.outcome in {
        AnswerOutcome.INSUFFICIENT_EVIDENCE,
        AnswerOutcome.CONFLICTING_EVIDENCE,
        AnswerOutcome.PARTIALLY_ANSWERED,
    }:
        structured = align_structured_with_behavior(structured, behavior)

    composed = compose_employee_answer(structured.answer, behavior)
    selected = selected_evidence_ids(structured, items, behavior)
    composed = append_source_references(composed, items, selected)

    return GroundedAnswer(
        question=safe_query,
        structured=structured,
        behavior=behavior,
        evidence_items=items,
        selected_ids=selected,
        composed_answer=composed,
        retrieval_error=retrieval_error,
    )

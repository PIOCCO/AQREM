from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.enums import AnswerOutcome
from app.services.answering.service import _evidence_blocks
from app.services.library.service import AnswerLibraryService
from app.services.llm.base import AnswerRequest, StructuredAnswer
from app.services.llm.factory import get_llm_provider
from app.services.llm.guardrails import (
    clamp_question,
    sanitize_evidence_content,
    validate_structured_answer,
    wrap_evidence_for_prompt,
)
from app.services.rag.behavior import (
    BehaviorResult,
    classify_behavior,
    classify_early_behavior,
    compose_employee_answer,
)
from app.services.retrieval.service import RetrievalService
from app.schemas.evidence import EvidenceItemSummaryResponse


def _behavior_payload(behavior: BehaviorResult) -> dict:
    return {
        "outcome": behavior.outcome.value,
        "missing_information": list(behavior.missing_information),
        "next_steps": list(behavior.next_steps),
        "needs_review": behavior.needs_review,
        "conflicts": [
            {"topic": c.topic, "detail": c.detail, "source_paths": list(c.source_paths)}
            for c in behavior.conflicts
        ],
    }


def _outcome_skips_llm(behavior: BehaviorResult) -> bool:
    return behavior.outcome in {
        AnswerOutcome.ACTION_NOT_SUPPORTED,
        AnswerOutcome.ACCESS_DENIED,
        AnswerOutcome.CLARIFICATION_REQUIRED,
        AnswerOutcome.SOURCE_UNAVAILABLE,
    }


class ChatAskService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _build_citations(
        self,
        items: list,
        selected_ids: set[UUID],
    ) -> list[EvidenceItemSummaryResponse]:
        citations: list[EvidenceItemSummaryResponse] = []
        for item in items:
            if item.id not in selected_ids:
                continue
            citations.append(
                EvidenceItemSummaryResponse(
                    id=item.id,
                    organization_id=item.organization_id,
                    project_id=item.project_id,
                    source_id=item.source_id,
                    source_type=item.source_type,
                    scope=item.scope,
                    file_name=item.file_name,
                    file_path=item.file_path,
                    content=sanitize_evidence_content(item.content),
                    content_truncated=len(item.content or "") > 2000,
                    content_type=item.content_type,
                    language=item.language,
                    repository=item.repository,
                    branch=item.branch,
                    commit_hash=item.commit_hash,
                    line_start=item.line_start,
                    line_end=item.line_end,
                    symbol_name=item.symbol_name,
                    symbol_kind=item.symbol_kind,
                    evidence_strength=item.evidence_strength,
                    chunk_index=item.chunk_index,
                    created_at=item.created_at,
                )
            )
        return citations

    async def ask(
        self,
        *,
        organization_id: UUID,
        query: str,
        project_id: UUID | None,
        user_id: UUID | None = None,
    ) -> dict:
        safe_query = clamp_question(query)
        settings = get_settings()
        limit = min(8, settings.llm_max_retrieval_results)

        library = AnswerLibraryService(self.db)
        entries = library.search_entries(
            organization_id=organization_id,
            query=safe_query,
            project_id=project_id,
            limit=3,
        )
        approved = next((e for e in entries if e.status == "approved"), None)
        if approved and approved.answer_text.strip():
            return {
                "query": safe_query,
                "answer": approved.answer_text.strip(),
                "confidence": "high",
                "evidence_sufficiency": "sufficient",
                "reasoning_summary": f"Reused approved library entry for: {approved.question_text}",
                "is_draft": False,
                "from_library": True,
                "library_entry_id": approved.id,
                "citations": [],
                "outcome": AnswerOutcome.ANSWERED.value,
                "missing_information": [],
                "next_steps": [],
                "needs_review": False,
                "conflicts": [],
            }

        retrieval_error: str | None = None
        items: list = []
        try:
            items = await RetrievalService(self.db).retrieve(
                organization_id=organization_id,
                query=safe_query,
                project_id=project_id,
                limit=limit,
            )
            items = [i for i in items if i.organization_id == organization_id]
        except Exception:
            retrieval_error = "retrieval_failed"

        pre_behavior = classify_early_behavior(
            question=safe_query,
            retrieval_error=retrieval_error,
        )
        if pre_behavior and _outcome_skips_llm(pre_behavior):
            answer = compose_employee_answer("", pre_behavior)
            return {
                "query": safe_query,
                "answer": answer,
                "confidence": "low",
                "evidence_sufficiency": "insufficient",
                "reasoning_summary": None,
                "is_draft": True,
                "from_library": False,
                "library_entry_id": None,
                "citations": [],
                **_behavior_payload(pre_behavior),
            }

        if not items:
            empty_behavior = classify_behavior(
                question=safe_query,
                evidence_items=[],
                llm_sufficiency="insufficient",
                retrieval_error=None,
            )
            base = (
                "No supporting documents were retrieved for this question in your connected, indexed sources."
            )
            return {
                "query": safe_query,
                "answer": compose_employee_answer(base, empty_behavior),
                "confidence": "low",
                "evidence_sufficiency": "insufficient",
                "reasoning_summary": "No evidence items matched the query in the current scope.",
                "is_draft": True,
                "from_library": False,
                "library_entry_id": None,
                "citations": [],
                **_behavior_payload(empty_behavior),
            }

        blocks = wrap_evidence_for_prompt(_evidence_blocks(items))
        allowed_ids = {str(i.id) for i in items}

        llm = get_llm_provider()
        structured = await llm.generate_answer(
            AnswerRequest(question=safe_query, evidence_blocks=blocks),
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
            structured = self._align_structured_with_behavior(structured, behavior)

        answer_text = compose_employee_answer(structured.answer, behavior)

        selected_ids = self._selected_evidence_ids(structured, items, behavior)

        citations = self._build_citations(items, selected_ids)

        return {
            "query": safe_query,
            "answer": answer_text,
            "confidence": structured.confidence,
            "evidence_sufficiency": structured.evidence_sufficiency,
            "reasoning_summary": structured.reasoning_summary,
            "is_draft": True,
            "from_library": False,
            "library_entry_id": None,
            "citations": citations,
            **_behavior_payload(behavior),
        }

    @staticmethod
    def _align_structured_with_behavior(
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

    @staticmethod
    def _selected_evidence_ids(
        structured: StructuredAnswer,
        items: list,
        behavior: BehaviorResult,
    ) -> set[UUID]:
        if behavior.outcome in {
            AnswerOutcome.INSUFFICIENT_EVIDENCE,
            AnswerOutcome.ACCESS_DENIED,
            AnswerOutcome.SOURCE_UNAVAILABLE,
        }:
            return set()

        selected_ids = {UUID(x) for x in structured.evidence_ids if x}
        if not selected_ids and items and structured.evidence_sufficiency != "insufficient":
            selected_ids = {item.id for item in items[:3]}
        if behavior.outcome == AnswerOutcome.CONFLICTING_EVIDENCE and items:
            selected_ids = {item.id for item in items[:6]}
        return selected_ids

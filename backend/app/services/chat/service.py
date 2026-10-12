from uuid import UUID

from sqlalchemy.orm import Session

from app.models.enums import AnswerOutcome
from app.services.library.service import AnswerLibraryService
from app.services.llm.guardrails import clamp_question, sanitize_evidence_content
from app.services.rag.behavior import BehaviorResult
from app.services.rag.grounding import generate_grounded_answer, selected_evidence_ids
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

        grounded = await generate_grounded_answer(
            self.db,
            organization_id=organization_id,
            question=safe_query,
            project_id=project_id,
        )
        structured = grounded.structured
        behavior = grounded.behavior
        items = grounded.evidence_items
        selected = grounded.selected_ids
        if not selected and items:
            selected = selected_evidence_ids(structured, items, behavior)

        citations = self._build_citations(items, selected)

        return {
            "query": safe_query,
            "answer": grounded.composed_answer,
            "confidence": structured.confidence,
            "evidence_sufficiency": structured.evidence_sufficiency,
            "reasoning_summary": structured.reasoning_summary,
            "is_draft": True,
            "from_library": False,
            "library_entry_id": None,
            "citations": citations,
            **_behavior_payload(behavior),
        }

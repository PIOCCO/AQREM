from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.answering.service import _evidence_blocks
from app.services.library.service import AnswerLibraryService
from app.services.llm.base import AnswerRequest
from app.services.llm.factory import get_llm_provider
from app.services.llm.guardrails import (
    clamp_question,
    sanitize_evidence_content,
    validate_structured_answer,
    wrap_evidence_for_prompt,
)
from app.services.retrieval.service import RetrievalService
from app.schemas.evidence import EvidenceItemSummaryResponse


class ChatAskService:
    def __init__(self, db: Session) -> None:
        self.db = db

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

        # Optional library shortcut (same org/project scope as answering)
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
            }

        items = await RetrievalService(self.db).retrieve(
            organization_id=organization_id,
            query=safe_query,
            project_id=project_id,
            limit=limit,
        )
        items = [i for i in items if i.organization_id == organization_id]
        blocks = wrap_evidence_for_prompt(_evidence_blocks(items))
        allowed_ids = {str(i.id) for i in items}

        llm = get_llm_provider()
        structured = await llm.generate_answer(
            AnswerRequest(question=safe_query, evidence_blocks=blocks),
        )
        structured = validate_structured_answer(structured, allowed_evidence_ids=allowed_ids)

        selected_ids = {UUID(x) for x in structured.evidence_ids if x}
        if not selected_ids and items and structured.evidence_sufficiency != "insufficient":
            selected_ids = {item.id for item in items[:3]}

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

        return {
            "query": safe_query,
            "answer": structured.answer,
            "confidence": structured.confidence,
            "evidence_sufficiency": structured.evidence_sufficiency,
            "reasoning_summary": structured.reasoning_summary,
            "is_draft": True,
            "from_library": False,
            "library_entry_id": None,
            "citations": citations,
        }

import asyncio
import json
import time
from collections.abc import AsyncIterator
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.enums import AnswerOutcome
from app.models.project import Project
from app.models.source import Source
from app.schemas.evidence import EvidenceItemSummaryResponse
from app.services.chat.intent import build_conversational_answer, classify_chat_intent
from app.services.chat.messages import (
    format_empty_retrieval_message,
    format_insufficient_evidence_message,
)
from app.services.library.service import AnswerLibraryService
from app.core.config import get_settings
from app.services.llm.errors import ModelServiceError
from app.services.llm.factory import get_llm_provider
from app.services.llm.gateway import GatewayLLMProvider, evidence_ids_mentioned
from app.services.llm.guardrails import clamp_question, sanitize_evidence_content, wrap_evidence_for_prompt
from app.services.llm.prompts import CHAT_STREAM_SYSTEM
from app.services.rag.grounding import evidence_blocks, generate_grounded_answer, selected_evidence_ids
from app.services.retrieval.debug_log import log_rag_event
from app.services.retrieval.scope import count_org_evidence_chunks
from app.services.retrieval.service import RetrievalService
from app.services.rag.behavior import BehaviorResult
from app.core.roles import Role
from app.core.tenant import TenantContext
from app.models.organization import OrganizationMembership
from app.services.access_control.context import UserAccessContext, build_access_context


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


def _project_label(db: Session, project_id: UUID | None) -> str | None:
    if project_id is None:
        return None
    project = db.get(Project, project_id)
    return project.name if project else None


def _count_project_sources(db: Session, organization_id: UUID, project_id: UUID | None) -> int:
    q = db.query(Source).filter(Source.organization_id == organization_id)
    if project_id is not None:
        q = q.filter(Source.project_id == project_id)
    return q.count()


def _empty_retrieval_payload(
    *,
    db: Session,
    organization_id: UUID,
    project_id: UUID | None,
    project_name: str | None,
    sources_searched: int,
) -> dict:
    org_chunks = count_org_evidence_chunks(db, organization_id=organization_id, project_id=project_id)
    return {
        "answer": format_empty_retrieval_message(org_chunk_count=org_chunks),
        "confidence": "low",
        "evidence_sufficiency": "insufficient",
        "reasoning_summary": None,
        "is_draft": False,
        "from_library": False,
        "library_entry_id": None,
        "citations": [],
        "outcome": AnswerOutcome.INSUFFICIENT_EVIDENCE.value,
        "conversational": False,
        "missing_information": [],
        "next_steps": [],
        "needs_review": False,
        "conflicts": [],
        "project_name": project_name,
        "sources_searched": sources_searched,
        "query_time_ms": 0,
    }


class ChatAskService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _resolve_access(
        self,
        *,
        organization_id: UUID,
        user_id: UUID | None,
        access: UserAccessContext | None,
    ) -> UserAccessContext | None:
        if access is not None:
            return access
        if user_id is None:
            return None
        membership = (
            self.db.query(OrganizationMembership)
            .filter(
                OrganizationMembership.organization_id == organization_id,
                OrganizationMembership.user_id == user_id,
            )
            .first()
        )
        if membership is None:
            return None
        tenant = TenantContext(
            user_id=user_id,
            organization_id=organization_id,
            role=Role(membership.role),
            email="",
        )
        return build_access_context(self.db, tenant)

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
        access: UserAccessContext | None = None,
    ) -> dict:
        safe_query = clamp_question(query)
        access = self._resolve_access(
            organization_id=organization_id, user_id=user_id, access=access
        )
        project_name = _project_label(self.db, project_id)
        sources_searched = _count_project_sources(self.db, organization_id, project_id)

        intent = classify_chat_intent(safe_query)
        if intent:
            return {
                "query": safe_query,
                "answer": build_conversational_answer(intent),
                "confidence": "high",
                "evidence_sufficiency": "not_applicable",
                "reasoning_summary": None,
                "is_draft": False,
                "from_library": False,
                "library_entry_id": None,
                "citations": [],
                "outcome": "conversational",
                "intent": intent,
                "conversational": True,
                "missing_information": [],
                "next_steps": [],
                "needs_review": False,
                "conflicts": [],
                "project_name": project_name,
                "sources_searched": sources_searched,
                "query_time_ms": 0,
            }

        library = AnswerLibraryService(self.db)
        entries = library.search_entries(
            organization_id=organization_id,
            query=safe_query,
            project_id=project_id,
            limit=3,
            access=access,
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
                "conversational": False,
                "project_name": project_name,
                "sources_searched": sources_searched,
                "query_time_ms": 0,
            }

        started = time.perf_counter()
        grounded = await generate_grounded_answer(
            self.db,
            organization_id=organization_id,
            question=safe_query,
            project_id=project_id,
            access=access,
        )
        query_time_ms = int((time.perf_counter() - started) * 1000)

        structured = grounded.structured
        behavior = grounded.behavior
        items = grounded.evidence_items
        selected = grounded.selected_ids
        if not selected and items:
            selected = selected_evidence_ids(structured, items, behavior)

        citations = self._build_citations(items, selected)
        answer = grounded.composed_answer
        if behavior.outcome == AnswerOutcome.INSUFFICIENT_EVIDENCE and items:
            answer = format_insufficient_evidence_message(
                project_name=project_name,
                sources_searched=sources_searched,
            )

        return {
            "query": safe_query,
            "answer": answer,
            "confidence": structured.confidence,
            "evidence_sufficiency": structured.evidence_sufficiency,
            "reasoning_summary": structured.reasoning_summary,
            "is_draft": True,
            "from_library": False,
            "library_entry_id": None,
            "citations": citations,
            "conversational": False,
            "project_name": project_name,
            "sources_searched": sources_searched,
            "query_time_ms": query_time_ms,
            **_behavior_payload(behavior),
        }

    async def ask_stream(
        self,
        *,
        organization_id: UUID,
        query: str,
        project_id: UUID | None,
        user_id: UUID | None = None,
        access: UserAccessContext | None = None,
        cancel_event: asyncio.Event | None = None,
    ) -> AsyncIterator[dict]:
        """Yield stream events: token, meta, or error."""
        safe_query = clamp_question(query)
        access = self._resolve_access(
            organization_id=organization_id, user_id=user_id, access=access
        )
        project_name = _project_label(self.db, project_id)
        sources_searched = _count_project_sources(self.db, organization_id, project_id)

        async def _stream_text(text: str, meta: dict) -> AsyncIterator[dict]:
            for ch in text:
                if cancel_event and cancel_event.is_set():
                    return
                yield {"type": "token", "text": ch}
            yield {"type": "meta", **meta}

        intent = classify_chat_intent(safe_query)
        if intent:
            text = build_conversational_answer(intent)
            async for ev in _stream_text(
                text,
                {
                    "conversational": True,
                    "outcome": "conversational",
                    "intent": intent,
                    "citations": [],
                    "is_draft": False,
                },
            ):
                yield ev
            return

        settings = get_settings()
        llm = get_llm_provider(organization_id)
        if not isinstance(llm, GatewayLLMProvider):
            result = await self.ask(
                organization_id=organization_id,
                query=safe_query,
                project_id=project_id,
                user_id=user_id,
                access=access,
            )
            async for ev in _stream_text(
                result["answer"],
                {
                    "conversational": result.get("conversational", False),
                    "outcome": result.get("outcome"),
                    "citations": [c.model_dump() for c in result.get("citations", [])],
                    "is_draft": result.get("is_draft", True),
                    "evidence_sufficiency": result.get("evidence_sufficiency"),
                },
            ):
                yield ev
            return

        top_k = min(8, settings.llm_max_retrieval_results)
        items = await RetrievalService(self.db).retrieve(
            organization_id=organization_id,
            query=safe_query,
            project_id=project_id,
            limit=top_k,
            access=access,
        )
        items = [i for i in items if i.organization_id == organization_id]
        if not items:
            payload = _empty_retrieval_payload(
                db=self.db,
                organization_id=organization_id,
                project_id=project_id,
                project_name=project_name,
                sources_searched=sources_searched,
            )
            log_rag_event(
                "stream_empty_retrieval",
                organization_id=organization_id,
                project_id=project_id,
                answer=payload["answer"],
            )
            async for ev in _stream_text(
                payload["answer"],
                {
                    "conversational": False,
                    "outcome": payload["outcome"],
                    "citations": [],
                    "is_draft": payload["is_draft"],
                    "evidence_sufficiency": payload["evidence_sufficiency"],
                    "project_name": project_name,
                    "sources_searched": sources_searched,
                },
            ):
                yield ev
            return

        blocks = wrap_evidence_for_prompt(evidence_blocks(items))
        log_rag_event(
            "stream_llm_context",
            organization_id=organization_id,
            project_id=project_id,
            context_chunk_count=len(blocks),
            context_files=[i.file_name for i in items[:5]],
        )
        allowed = {str(i.id) for i in items}
        user_payload = json.dumps({"question": safe_query, "evidence": blocks})
        messages = [
            {"role": "system", "content": CHAT_STREAM_SYSTEM},
            {"role": "user", "content": user_payload},
        ]
        buffer = ""
        try:
            async for token in llm.stream_chat_tokens(messages=messages, cancel_event=cancel_event):
                buffer += token
                yield {"type": "token", "text": token}
        except ModelServiceError as exc:
            yield {"type": "error", "code": exc.code, "message": exc.user_message, "retryable": exc.retryable}
            return

        mentioned = evidence_ids_mentioned(buffer, allowed)
        selected = {UUID(x) for x in mentioned}
        if not selected:
            selected = {items[0].id}
        citations = self._build_citations(items, selected)
        yield {
            "type": "meta",
            "conversational": False,
            "outcome": AnswerOutcome.ANSWERED.value,
            "citations": [c.model_dump(mode="json") for c in citations],
            "is_draft": True,
            "evidence_sufficiency": "sufficient",
            "project_name": project_name,
            "sources_searched": sources_searched,
        }

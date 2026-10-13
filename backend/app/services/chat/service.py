import time
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.enums import AnswerOutcome
from app.models.project import Project
from app.models.source import Source
from app.schemas.evidence import EvidenceItemSummaryResponse
from app.services.chat.intent import build_conversational_answer, classify_chat_intent
from app.services.chat.messages import format_insufficient_evidence_message
from app.services.library.service import AnswerLibraryService
from app.services.llm.guardrails import clamp_question, sanitize_evidence_content
from app.services.rag.behavior import BehaviorResult
from app.core.roles import Role
from app.core.tenant import TenantContext
from app.models.organization import OrganizationMembership
from app.services.access_control.context import UserAccessContext, build_access_context
from app.services.rag.grounding import generate_grounded_answer, selected_evidence_ids


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
        if behavior.outcome == AnswerOutcome.INSUFFICIENT_EVIDENCE:
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

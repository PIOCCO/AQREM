from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.audit.service import record_audit
from app.core.config import get_settings
from app.models.answer_library import AnswerLibraryEntry, AnswerLibraryEvidenceLink
from app.models.enums import AnswerGenerationSource, AnswerStatus, EvidenceScope, LibraryEntryStatus
from app.models.evidence import EvidenceItem
from app.models.questionnaire import Answer, AnswerEvidenceLink, Question, Questionnaire
from app.services.library.validation import evidence_item_in_project_scope, validate_library_evidence
from app.services.llm.factory import get_llm_provider
from app.services.questionnaire.normalize import normalize_question

SIMILARITY_THRESHOLD = 0.82


class AnswerLibraryService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()

    async def upsert_from_approved_answer(self, answer: Answer) -> AnswerLibraryEntry:
        question = self.db.get(Question, answer.question_id)
        if question is None:
            raise ValueError("Question not found")
        questionnaire = self.db.get(Questionnaire, question.questionnaire_id)
        project_id = questionnaire.project_id if questionnaire else None
        scope = EvidenceScope.PROJECT.value if project_id else EvidenceScope.ORGANIZATION.value

        text_value = answer.approved_text or answer.draft_text
        embedding = (await get_llm_provider().embed([question.normalized_text]))[0]

        entry = (
            self.db.query(AnswerLibraryEntry)
            .filter(AnswerLibraryEntry.source_answer_id == answer.id)
            .first()
        )
        if entry is None:
            entry = AnswerLibraryEntry(
                organization_id=answer.organization_id,
                project_id=project_id,
                scope=scope,
                source_answer_id=answer.id,
                question_text=question.text,
                normalized_question=question.normalized_text,
                answer_text=text_value,
                reviewer_id=answer.reviewer_id,
                approved_at=answer.approved_at or datetime.now(UTC),
                question_embedding=embedding,
            )
            self.db.add(entry)
        else:
            entry.question_text = question.text
            entry.normalized_question = question.normalized_text
            entry.answer_text = text_value
            entry.project_id = project_id
            entry.scope = scope
            entry.version += 1
            entry.status = LibraryEntryStatus.APPROVED.value
            entry.reviewer_id = answer.reviewer_id
            entry.approved_at = answer.approved_at or datetime.now(UTC)
            entry.question_embedding = embedding

        self.db.flush()
        self.db.query(AnswerLibraryEvidenceLink).filter(
            AnswerLibraryEvidenceLink.library_entry_id == entry.id
        ).delete(synchronize_session=False)

        links = (
            self.db.query(AnswerEvidenceLink)
            .filter(AnswerEvidenceLink.answer_id == answer.id)
            .all()
        )
        for link in links:
            item = self.db.get(EvidenceItem, link.evidence_item_id)
            if item is None:
                continue
            self.db.add(
                AnswerLibraryEvidenceLink(
                    library_entry_id=entry.id,
                    evidence_item_id=item.id,
                    snapshot_content_hash=item.content_hash,
                    file_path=item.file_path,
                    evidence_strength=link.evidence_strength or item.evidence_strength,
                )
            )

        self.db.flush()
        record_audit(
            self.db,
            organization_id=answer.organization_id,
            user_id=answer.reviewer_id,
            action="answer_library_upserted",
            resource_type="answer_library_entry",
            resource_id=str(entry.id),
            metadata={"source_answer_id": str(answer.id), "version": entry.version},
        )
        return entry

    async def find_similar_entries(
        self,
        *,
        organization_id: UUID,
        normalized_question: str,
        project_id: UUID | None,
        limit: int = 5,
    ) -> list[tuple[AnswerLibraryEntry, float]]:
        embedding = (await get_llm_provider().embed([normalized_question]))[0]
        embedding_literal = "[" + ",".join(str(x) for x in embedding) + "]"

        scope_filter = "organization_id = :org_id AND status = 'approved'"
        params: dict = {"org_id": str(organization_id), "limit": limit, "embedding": embedding_literal}
        if project_id:
            scope_filter += (
                " AND (project_id = :project_id OR (project_id IS NULL AND scope = 'organization'))"
            )
            params["project_id"] = str(project_id)

        rows = self.db.execute(
            text(
                f"""
                SELECT id, 1 - (question_embedding <=> CAST(:embedding AS vector)) AS score
                FROM answer_library_entries
                WHERE {scope_filter} AND question_embedding IS NOT NULL
                ORDER BY score DESC
                LIMIT :limit
                """
            ),
            params,
        ).fetchall()
        if not rows:
            return []

        ids = [row[0] for row in rows if row[1] is not None and float(row[1]) >= SIMILARITY_THRESHOLD]
        if not ids:
            return []

        entries = self.db.query(AnswerLibraryEntry).filter(AnswerLibraryEntry.id.in_(ids)).all()
        score_map = {row[0]: float(row[1]) for row in rows}
        ranked = sorted(entries, key=lambda e: score_map.get(e.id, 0), reverse=True)
        return [(entry, score_map.get(entry.id, 0.0)) for entry in ranked]

    async def try_reuse_for_question(
        self,
        *,
        question: Question,
        questionnaire: Questionnaire,
        user_id: UUID | None,
    ) -> Answer | None:
        candidates = await self.find_similar_entries(
            organization_id=question.organization_id,
            normalized_question=question.normalized_text,
            project_id=questionnaire.project_id,
            limit=3,
        )
        if not candidates:
            return None

        for entry, score in candidates:
            validation = validate_library_evidence(self.db, entry)
            if not validation.valid:
                entry.status = LibraryEntryStatus.NEEDS_REVIEW.value
                self.db.flush()
                continue

            if questionnaire.project_id:
                links = (
                    self.db.query(AnswerLibraryEvidenceLink)
                    .filter(AnswerLibraryEvidenceLink.library_entry_id == entry.id)
                    .all()
                )
                scoped_ok = True
                for link in links:
                    if not link.evidence_item_id:
                        scoped_ok = False
                        break
                    item = self.db.get(EvidenceItem, link.evidence_item_id)
                    if item is None or not evidence_item_in_project_scope(item, questionnaire.project_id):
                        scoped_ok = False
                        break
                if not scoped_ok:
                    continue

            answer = question.answer
            if answer is None:
                answer = Answer(organization_id=question.organization_id, question_id=question.id)
                self.db.add(answer)
            else:
                answer.version += 1

            exact_match = question.normalized_text == entry.normalized_question
            answer.draft_text = entry.answer_text
            answer.confidence = "high" if exact_match else "medium"
            answer.evidence_sufficiency = "sufficient"
            answer.generation_source = (
                AnswerGenerationSource.LIBRARY_REUSE.value
                if exact_match
                else AnswerGenerationSource.LIBRARY_ADAPTED.value
            )
            answer.library_entry_id = entry.id
            answer.status = AnswerStatus.NEEDS_REVIEW.value
            answer.reasoning_summary = (
                f"Reused approved library entry (similarity {score:.2f}). "
                f"Evidence validation passed ({validation.checked_count} citations)."
            )
            answer.reviewer_id = None
            answer.approved_text = None
            answer.approved_at = None
            answer.potentially_stale = False
            self.db.flush()

            self.db.query(AnswerEvidenceLink).filter(AnswerEvidenceLink.answer_id == answer.id).delete(
                synchronize_session=False
            )
            for link in (
                self.db.query(AnswerLibraryEvidenceLink)
                .filter(AnswerLibraryEvidenceLink.library_entry_id == entry.id)
                .all()
            ):
                if link.evidence_item_id is None:
                    continue
                self.db.add(
                    AnswerEvidenceLink(
                        answer_id=answer.id,
                        evidence_item_id=link.evidence_item_id,
                        evidence_strength=link.evidence_strength,
                    )
                )

            entry.reuse_count += 1
            record_audit(
                self.db,
                organization_id=question.organization_id,
                user_id=user_id,
                action="answer_reused_from_library",
                resource_type="question",
                resource_id=str(question.id),
                metadata={
                    "library_entry_id": str(entry.id),
                    "similarity": score,
                    "generation_source": answer.generation_source,
                },
            )
            self.db.flush()
            return answer

        return None

    def search_entries(
        self,
        *,
        organization_id: UUID,
        query: str | None = None,
        project_id: UUID | None = None,
        limit: int = 50,
    ) -> list[AnswerLibraryEntry]:
        q = self.db.query(AnswerLibraryEntry).filter(
            AnswerLibraryEntry.organization_id == organization_id
        )
        if project_id:
            q = q.filter(
                (AnswerLibraryEntry.project_id == project_id)
                | (
                    (AnswerLibraryEntry.project_id.is_(None))
                    & (AnswerLibraryEntry.scope == EvidenceScope.ORGANIZATION.value)
                )
            )
        if query:
            normalized = normalize_question(query)
            q = q.filter(
                AnswerLibraryEntry.normalized_question.contains(normalized[:120])
                | AnswerLibraryEntry.question_text.ilike(f"%{query[:120]}%")
            )
        return q.order_by(AnswerLibraryEntry.updated_at.desc()).limit(limit).all()

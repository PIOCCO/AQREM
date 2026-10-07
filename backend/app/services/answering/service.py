from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.audit.service import record_audit
from app.models.enums import AnswerGenerationSource, AnswerStatus, QuestionnaireStatus
from app.models.evidence import EvidenceItem
from app.models.questionnaire import Answer, AnswerEvidenceLink, Question, Questionnaire
from app.services.library.service import AnswerLibraryService
from app.core.config import get_settings
from app.services.llm.base import AnswerRequest
from app.services.llm.factory import get_llm_provider
from app.services.llm.guardrails import (
    clamp_question,
    sanitize_evidence_content,
    validate_structured_answer,
    wrap_evidence_for_prompt,
)
from app.services.retrieval.service import RetrievalService


def _evidence_blocks(items: list[EvidenceItem]) -> list[dict]:
    blocks: list[dict] = []
    for item in items:
        blocks.append(
            {
                "id": str(item.id),
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


def _status_for_result(sufficiency: str) -> str:
    if sufficiency == "insufficient":
        return AnswerStatus.DRAFT.value
    return AnswerStatus.NEEDS_REVIEW.value


class AnsweringService:
    def __init__(self, db: Session) -> None:
        self.db = db

    async def generate_for_question(
        self,
        *,
        question: Question,
        user_id: UUID | None = None,
        top_k: int = 6,
        skip_library_reuse: bool = False,
        stale_regeneration: bool = False,
    ) -> Answer:
        questionnaire = self.db.get(Questionnaire, question.questionnaire_id)
        if questionnaire is None:
            raise ValueError("Questionnaire not found")

        answer = question.answer
        if answer is None:
            answer = (
                self.db.query(Answer).filter(Answer.question_id == question.id).first()
            )
        preserved_approved = answer.approved_text if answer else None

        if stale_regeneration and answer is not None:
            answer.regeneration_backup = {
                "approved_text": answer.approved_text,
                "draft_text": answer.draft_text,
                "status": answer.status,
            }

        if not skip_library_reuse:
            reused = await AnswerLibraryService(self.db).try_reuse_for_question(
                question=question,
                questionnaire=questionnaire,
                user_id=user_id,
            )
            if reused is not None:
                return reused

        settings = get_settings()
        top_k = min(top_k, settings.llm_max_retrieval_results)
        evidence_items = await RetrievalService(self.db).retrieve(
            organization_id=question.organization_id,
            query=clamp_question(question.text),
            project_id=questionnaire.project_id,
            limit=top_k,
        )
        evidence_items = [
            i for i in evidence_items if i.organization_id == question.organization_id
        ]
        blocks = wrap_evidence_for_prompt(_evidence_blocks(evidence_items))
        allowed_ids = {str(i.id) for i in evidence_items}

        llm = get_llm_provider()
        structured = await llm.generate_answer(
            AnswerRequest(
                question=clamp_question(question.text),
                evidence_blocks=blocks,
            )
        )
        structured = validate_structured_answer(structured, allowed_evidence_ids=allowed_ids)

        if answer is None:
            answer = Answer(
                organization_id=question.organization_id,
                question_id=question.id,
            )
            self.db.add(answer)
        else:
            answer.version += 1

        answer.draft_text = structured.answer
        answer.confidence = structured.confidence
        answer.evidence_sufficiency = structured.evidence_sufficiency
        if stale_regeneration:
            answer.generation_source = AnswerGenerationSource.STALE_REGENERATION.value
            answer.reasoning_summary = (
                "Regenerated because supporting evidence changed. "
                + (structured.reasoning_summary or "")
            ).strip()
            answer.status = AnswerStatus.NEEDS_REVIEW.value
            answer.approved_text = preserved_approved
            answer.potentially_stale = True
        else:
            answer.generation_source = AnswerGenerationSource.RETRIEVAL_LLM.value
            answer.reasoning_summary = structured.reasoning_summary
            answer.status = _status_for_result(structured.evidence_sufficiency)
            answer.reviewer_id = None
            answer.approved_at = None
            answer.approved_text = None
            answer.potentially_stale = False
            answer.stale_detected_at = None
            answer.stale_reason = None
        answer.library_entry_id = None
        if not stale_regeneration:
            answer.reviewer_id = None
            answer.approved_at = None
        self.db.flush()

        self.db.query(AnswerEvidenceLink).filter(AnswerEvidenceLink.answer_id == answer.id).delete(
            synchronize_session=False
        )
        selected_ids = {UUID(x) for x in structured.evidence_ids if x}
        if not selected_ids and evidence_items and structured.evidence_sufficiency != "insufficient":
            selected_ids = {item.id for item in evidence_items[:3]}

        for item in evidence_items:
            if item.id not in selected_ids:
                continue
            self.db.add(
                AnswerEvidenceLink(
                    answer_id=answer.id,
                    evidence_item_id=item.id,
                    evidence_strength=item.evidence_strength,
                )
            )

        if questionnaire.status == QuestionnaireStatus.DRAFT.value:
            questionnaire.status = QuestionnaireStatus.IN_PROGRESS.value

        action = "answer_regenerated" if stale_regeneration else "answer_generated"
        record_audit(
            self.db,
            organization_id=question.organization_id,
            user_id=user_id,
            action=action,
            resource_type="question",
            resource_id=str(question.id),
            metadata={
                "confidence": answer.confidence,
                "evidence_sufficiency": answer.evidence_sufficiency,
                "evidence_count": len(selected_ids),
                "stale_regeneration": stale_regeneration,
            },
        )
        self.db.flush()
        return answer

    async def approve_answer(self, answer: Answer, reviewer_id: UUID) -> Answer:
        was_stale = answer.potentially_stale
        answer.approved_text = answer.draft_text
        answer.status = AnswerStatus.APPROVED.value
        answer.reviewer_id = reviewer_id
        answer.approved_at = datetime.now(UTC)
        from app.services.staleness.service import StalenessService

        StalenessService(self.db).clear_stale_after_approval(answer)
        record_audit(
            self.db,
            organization_id=answer.organization_id,
            user_id=reviewer_id,
            action="stale_answer_approved" if was_stale else "answer_approved",
            resource_type="answer",
            resource_id=str(answer.id),
        )
        await AnswerLibraryService(self.db).upsert_from_approved_answer(answer)
        self._refresh_questionnaire_status(answer)
        return answer

    async def edit_answer(self, answer: Answer, reviewer_id: UUID, text: str) -> Answer:
        answer.draft_text = text
        answer.approved_text = text
        answer.status = AnswerStatus.APPROVED.value
        answer.reviewer_id = reviewer_id
        answer.approved_at = datetime.now(UTC)
        answer.version += 1
        record_audit(
            self.db,
            organization_id=answer.organization_id,
            user_id=reviewer_id,
            action="answer_edited",
            resource_type="answer",
            resource_id=str(answer.id),
        )
        await AnswerLibraryService(self.db).upsert_from_approved_answer(answer)
        self._refresh_questionnaire_status(answer)
        return answer

    def reject_answer(self, answer: Answer, reviewer_id: UUID) -> Answer:
        backup = answer.regeneration_backup or {}
        if backup:
            answer.draft_text = backup.get("draft_text") or answer.draft_text
            answer.approved_text = backup.get("approved_text")
            answer.status = backup.get("status") or AnswerStatus.APPROVED.value
            answer.regeneration_backup = None
            action = "stale_answer_rejected"
        else:
            answer.status = AnswerStatus.REJECTED.value
            action = "answer_rejected"
        answer.reviewer_id = reviewer_id
        record_audit(
            self.db,
            organization_id=answer.organization_id,
            user_id=reviewer_id,
            action=action,
            resource_type="answer",
            resource_id=str(answer.id),
        )
        return answer

    def _refresh_questionnaire_status(self, answer: Answer) -> None:
        question = self.db.get(Question, answer.question_id)
        if question is None:
            return
        questionnaire = self.db.get(Questionnaire, question.questionnaire_id)
        if questionnaire is None:
            return
        questions = (
            self.db.query(Question).filter(Question.questionnaire_id == questionnaire.id).all()
        )
        answers = [q.answer for q in questions if q.answer is not None]
        if answers and all(a.status == AnswerStatus.APPROVED.value for a in answers):
            questionnaire.status = QuestionnaireStatus.COMPLETED.value
        elif any(a.status == AnswerStatus.NEEDS_REVIEW.value for a in answers):
            questionnaire.status = QuestionnaireStatus.IN_REVIEW.value

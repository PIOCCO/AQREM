from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.audit.service import record_audit
from app.models.answer_library import AnswerLibraryEntry
from app.models.enums import AnswerStatus, LibraryEntryStatus, StalenessEventStatus
from app.models.evidence import EvidenceItem
from app.models.project import Project
from app.models.questionnaire import Answer, Question, Questionnaire
from app.models.staleness import AnswerStalenessEvent
from app.services.library.validation import validate_library_evidence


class StalenessService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_stale_answers(
        self,
        *,
        organization_id: UUID,
        project_id: UUID | None = None,
        status: str | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Answer], int]:
        query = (
            self.db.query(Answer)
            .join(Question, Question.id == Answer.question_id)
            .join(Questionnaire, Questionnaire.id == Question.questionnaire_id)
            .filter(Answer.organization_id == organization_id, Answer.potentially_stale.is_(True))
        )
        if project_id:
            query = query.filter(Questionnaire.project_id == project_id)
        if status == "potentially_stale":
            query = query.filter(Answer.potentially_stale.is_(True))
        elif status == "needs_review":
            query = query.filter(Answer.status == AnswerStatus.NEEDS_REVIEW.value)
        if search:
            query = query.filter(
                or_(Question.text.ilike(f"%{search}%"), Question.external_id.ilike(f"%{search}%"))
            )

        total = query.count()
        rows = (
            query.options(joinedload(Answer.question).joinedload(Question.questionnaire))
            .order_by(Answer.stale_detected_at.desc().nullslast(), Answer.updated_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return rows, total

    def get_stale_answer_detail(self, *, organization_id: UUID, answer_id: UUID) -> dict | None:
        answer = (
            self.db.query(Answer)
            .options(joinedload(Answer.question).joinedload(Question.questionnaire))
            .filter(Answer.id == answer_id, Answer.organization_id == organization_id)
            .first()
        )
        if answer is None:
            return None

        question = answer.question
        questionnaire = question.questionnaire if question else None
        project = None
        if questionnaire and questionnaire.project_id:
            project = self.db.get(Project, questionnaire.project_id)

        events = (
            self.db.query(AnswerStalenessEvent)
            .filter(
                AnswerStalenessEvent.answer_id == answer.id,
                AnswerStalenessEvent.organization_id == organization_id,
                AnswerStalenessEvent.status == StalenessEventStatus.OPEN.value,
            )
            .order_by(AnswerStalenessEvent.detected_at.desc())
            .all()
        )

        changed_evidence = []
        for event in events:
            current_item = (
                self.db.get(EvidenceItem, event.evidence_item_id) if event.evidence_item_id else None
            )
            changed_evidence.append(
                {
                    "event_id": str(event.id),
                    "file_path": event.file_path,
                    "evidence_strength": event.evidence_strength,
                    "snapshot_content_hash": event.snapshot_content_hash,
                    "current_content_hash": event.current_content_hash,
                    "previous_commit_hash": event.previous_commit_hash,
                    "current_commit_hash": event.current_commit_hash
                    or (current_item.commit_hash if current_item else None),
                    "previous_content_excerpt": event.previous_content_excerpt,
                    "current_content_excerpt": event.current_content_excerpt
                    or (current_item.content[:500] if current_item else None),
                    "detected_at": event.detected_at.isoformat(),
                    "reason": event.reason,
                    "source_id": str(current_item.source_id) if current_item else None,
                }
            )

        library_entry = (
            self.db.query(AnswerLibraryEntry)
            .filter(AnswerLibraryEntry.source_answer_id == answer.id)
            .first()
        )

        return {
            "answer": answer,
            "question": question,
            "project": project,
            "questionnaire": questionnaire,
            "changed_evidence": changed_evidence,
            "library_entry_status": library_entry.status if library_entry else None,
        }

    def revalidate(self, *, organization_id: UUID, answer_id: UUID, user_id: UUID | None) -> dict:
        answer = self.db.get(Answer, answer_id)
        if answer is None or answer.organization_id != organization_id:
            raise ValueError("Answer not found")

        open_events = (
            self.db.query(AnswerStalenessEvent)
            .filter(
                AnswerStalenessEvent.answer_id == answer.id,
                AnswerStalenessEvent.status == StalenessEventStatus.OPEN.value,
            )
            .all()
        )

        changed: list[dict] = []
        current = True
        for event in open_events:
            item = self.db.get(EvidenceItem, event.evidence_item_id) if event.evidence_item_id else None
            if item is None:
                current = False
                changed.append({"file_path": event.file_path, "issue": "missing"})
                continue
            if item.content_hash != event.snapshot_content_hash:
                current = False
                changed.append(
                    {
                        "file_path": event.file_path,
                        "issue": "hash_mismatch",
                        "snapshot_content_hash": event.snapshot_content_hash,
                        "current_content_hash": item.content_hash,
                    }
                )

        library_entry = (
            self.db.query(AnswerLibraryEntry)
            .filter(AnswerLibraryEntry.source_answer_id == answer.id)
            .first()
        )
        if library_entry:
            validation = validate_library_evidence(self.db, library_entry)
            if not validation.valid:
                current = False

        status = AnswerStatus.NEEDS_REVIEW.value
        if current:
            self._clear_stale_state(answer)
            if answer.approved_text:
                answer.status = AnswerStatus.APPROVED.value
            status = answer.status
            if library_entry:
                library_entry.status = LibraryEntryStatus.APPROVED.value

        record_audit(
            self.db,
            organization_id=organization_id,
            user_id=user_id,
            action="stale_answer_revalidated",
            resource_type="answer",
            resource_id=str(answer.id),
            metadata={"current": current, "changed_evidence_count": len(changed)},
        )
        self.db.flush()
        return {
            "current": current,
            "status": status,
            "potentially_stale": answer.potentially_stale,
            "changed_evidence": changed,
        }

    def _clear_stale_state(self, answer: Answer) -> None:
        now = datetime.now(UTC)
        answer.potentially_stale = False
        answer.stale_detected_at = None
        answer.stale_reason = None
        self.db.query(AnswerStalenessEvent).filter(
            AnswerStalenessEvent.answer_id == answer.id,
            AnswerStalenessEvent.status == StalenessEventStatus.OPEN.value,
        ).update(
            {AnswerStalenessEvent.status: StalenessEventStatus.RESOLVED.value, AnswerStalenessEvent.resolved_at: now},
            synchronize_session=False,
        )

    def clear_stale_after_approval(self, answer: Answer) -> None:
        self._clear_stale_state(answer)
        answer.regeneration_backup = None

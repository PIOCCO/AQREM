from uuid import UUID

from sqlalchemy.orm import Session

from app.models.answer_library import AnswerLibraryEntry, AnswerLibraryEvidenceLink
from app.models.enums import LibraryEntryStatus
from app.models.questionnaire import Answer


def mark_entries_stale_for_evidence(db: Session, evidence_item_id: UUID) -> int:
    entry_ids = [
        row[0]
        for row in db.query(AnswerLibraryEvidenceLink.library_entry_id)
        .filter(AnswerLibraryEvidenceLink.evidence_item_id == evidence_item_id)
        .distinct()
        .all()
    ]
    if not entry_ids:
        return 0

    updated = (
        db.query(AnswerLibraryEntry)
        .filter(AnswerLibraryEntry.id.in_(entry_ids))
        .update({AnswerLibraryEntry.status: LibraryEntryStatus.NEEDS_REVIEW.value}, synchronize_session=False)
    )

    answer_ids = [
        row[0]
        for row in db.query(AnswerLibraryEntry.source_answer_id)
        .filter(AnswerLibraryEntry.id.in_(entry_ids))
        .all()
    ]
    if answer_ids:
        db.query(Answer).filter(Answer.id.in_(answer_ids)).update(
            {Answer.potentially_stale: True}, synchronize_session=False
        )
    return int(updated or 0)

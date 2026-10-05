from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.audit.service import record_audit
from app.models.answer_library import AnswerLibraryEntry, AnswerLibraryEvidenceLink
from app.models.enums import AnswerStatus, LibraryEntryStatus, StalenessEventStatus
from app.models.questionnaire import Answer, AnswerEvidenceLink
from app.models.staleness import AnswerStalenessEvent


def mark_evidence_changed(
    db: Session,
    *,
    organization_id: UUID,
    evidence_item_id: UUID,
    file_path: str,
    snapshot_content_hash: str,
    current_content_hash: str,
    previous_commit_hash: str | None,
    current_commit_hash: str | None,
    previous_content_excerpt: str | None,
    current_content_excerpt: str | None,
    evidence_strength: str | None,
    user_id: UUID | None = None,
) -> int:
    """Mark dependent answers/library entries stale and record change details."""
    reason = "Referenced evidence changed after the answer was approved."
    affected_answer_ids: set[UUID] = set()

    link_answer_ids = [
        row[0]
        for row in db.query(AnswerEvidenceLink.answer_id)
        .filter(AnswerEvidenceLink.evidence_item_id == evidence_item_id)
        .distinct()
        .all()
    ]
    affected_answer_ids.update(link_answer_ids)

    entry_ids = [
        row[0]
        for row in db.query(AnswerLibraryEvidenceLink.library_entry_id)
        .filter(AnswerLibraryEvidenceLink.evidence_item_id == evidence_item_id)
        .distinct()
        .all()
    ]
    if entry_ids:
        db.query(AnswerLibraryEntry).filter(AnswerLibraryEntry.id.in_(entry_ids)).update(
            {AnswerLibraryEntry.status: LibraryEntryStatus.NEEDS_REVIEW.value},
            synchronize_session=False,
        )
        source_answer_ids = [
            row[0]
            for row in db.query(AnswerLibraryEntry.source_answer_id)
            .filter(AnswerLibraryEntry.id.in_(entry_ids))
            .all()
        ]
        affected_answer_ids.update(source_answer_ids)

    marked = 0
    now = datetime.now(UTC)
    for answer_id in affected_answer_ids:
        answer = db.get(Answer, answer_id)
        if answer is None or answer.organization_id != organization_id:
            continue

        answer.potentially_stale = True
        answer.stale_detected_at = answer.stale_detected_at or now
        answer.stale_reason = reason
        if answer.status == AnswerStatus.APPROVED.value:
            answer.status = AnswerStatus.NEEDS_REVIEW.value

        db.add(
            AnswerStalenessEvent(
                organization_id=organization_id,
                answer_id=answer.id,
                evidence_item_id=evidence_item_id,
                file_path=file_path,
                snapshot_content_hash=snapshot_content_hash,
                current_content_hash=current_content_hash,
                previous_commit_hash=previous_commit_hash,
                current_commit_hash=current_commit_hash,
                previous_content_excerpt=previous_content_excerpt,
                current_content_excerpt=current_content_excerpt,
                evidence_strength=evidence_strength,
                reason=reason,
                status=StalenessEventStatus.OPEN.value,
            )
        )
        marked += 1
        record_audit(
            db,
            organization_id=organization_id,
            user_id=user_id,
            action="answer_marked_stale",
            resource_type="answer",
            resource_id=str(answer.id),
            metadata={"evidence_item_id": str(evidence_item_id), "file_path": file_path},
        )

    record_audit(
        db,
        organization_id=organization_id,
        user_id=user_id,
        action="evidence_changed",
        resource_type="evidence_item",
        resource_id=str(evidence_item_id),
        metadata={"file_path": file_path, "affected_answers": marked},
    )
    db.flush()
    return marked


# Backward-compatible alias used by indexer imports.
def mark_entries_stale_for_evidence(db: Session, evidence_item_id: UUID) -> int:
    from app.models.evidence import EvidenceItem

    item = db.get(EvidenceItem, evidence_item_id)
    if item is None:
        return 0
    return mark_evidence_changed(
        db,
        organization_id=item.organization_id,
        evidence_item_id=item.id,
        file_path=item.file_path,
        snapshot_content_hash=item.content_hash,
        current_content_hash=item.content_hash,
        previous_commit_hash=item.commit_hash,
        current_commit_hash=item.commit_hash,
        previous_content_excerpt=None,
        current_content_excerpt=item.content[:500] if item.content else None,
        evidence_strength=item.evidence_strength,
    )

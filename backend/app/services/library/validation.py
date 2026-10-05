from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.answer_library import AnswerLibraryEntry, AnswerLibraryEvidenceLink
from app.models.evidence import EvidenceItem


@dataclass
class EvidenceValidationResult:
    valid: bool
    missing_count: int
    changed_count: int
    checked_count: int
    details: list[str]


def validate_library_evidence(db: Session, entry: AnswerLibraryEntry) -> EvidenceValidationResult:
    links = (
        db.query(AnswerLibraryEvidenceLink)
        .filter(AnswerLibraryEvidenceLink.library_entry_id == entry.id)
        .all()
    )
    if not links:
        return EvidenceValidationResult(
            valid=False,
            missing_count=0,
            changed_count=0,
            checked_count=0,
            details=["Library entry has no linked evidence snapshots."],
        )

    missing = 0
    changed = 0
    details: list[str] = []
    for link in links:
        item = None
        if link.evidence_item_id:
            item = db.get(EvidenceItem, link.evidence_item_id)
        if item is None:
            missing += 1
            details.append(f"Missing evidence for {link.file_path}")
            continue
        if item.organization_id != entry.organization_id:
            missing += 1
            details.append(f"Evidence out of tenant scope: {link.file_path}")
            continue
        if item.content_hash != link.snapshot_content_hash:
            changed += 1
            details.append(f"Evidence changed: {link.file_path}")

    valid = missing == 0 and changed == 0
    return EvidenceValidationResult(
        valid=valid,
        missing_count=missing,
        changed_count=changed,
        checked_count=len(links),
        details=details,
    )


def evidence_item_in_project_scope(item: EvidenceItem, project_id: UUID | None) -> bool:
    if project_id is None:
        return True
    if item.project_id is None:
        return item.scope == "organization"
    return item.project_id == project_id

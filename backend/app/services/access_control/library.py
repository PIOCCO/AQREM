from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.answer_library import AnswerLibraryEntry, AnswerLibraryEvidenceLink
from app.models.evidence import EvidenceItem
from app.services.access_control.context import UserAccessContext
from app.services.access_control.policy import can_access_record


def library_entry_visible(db: Session, access: UserAccessContext | None, entry: AnswerLibraryEntry) -> bool:
    if access is None or access.is_org_admin:
        return True
    links = (
        db.query(AnswerLibraryEvidenceLink)
        .filter(AnswerLibraryEvidenceLink.library_entry_id == entry.id)
        .all()
    )
    if not links:
        return True
    for link in links:
        if link.evidence_item_id is None:
            return False
        item = db.get(EvidenceItem, link.evidence_item_id)
        if item is None:
            return False
        if not can_access_record(
            access,
            visibility_mode=item.visibility_mode,
            visibility_group_ids=item.visibility_group_ids,
            visibility_user_ids=item.visibility_user_ids,
        ):
            return False
    return True

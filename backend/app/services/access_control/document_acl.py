from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.client_admin import ClientDocument
from app.models.evidence import EvidenceItem
from app.models.source import Source
from app.core.config import get_settings
from app.services.access_control.constants import VISIBILITY_ADMINS_ONLY, VISIBILITY_ALL_STAFF, VISIBILITY_UNSET


def resolve_document_acl(
    db: Session,
    *,
    organization_id: UUID,
    source_id: UUID,
    file_name: str,
) -> tuple[str, list[UUID], list[UUID]]:
    if get_settings().product_v1:
        return VISIBILITY_ALL_STAFF, [], []
    doc = (
        db.query(ClientDocument)
        .filter(
            ClientDocument.organization_id == organization_id,
            ClientDocument.source_id == source_id,
            ClientDocument.file_name == file_name,
        )
        .order_by(ClientDocument.created_at.desc())
        .first()
    )
    if doc and doc.visibility_mode and doc.visibility_mode != VISIBILITY_UNSET:
        return (
            doc.visibility_mode,
            list(doc.visibility_group_ids or []),
            list(doc.visibility_user_ids or []),
        )
    source = db.get(Source, source_id)
    if source and source.visibility_mode and source.visibility_mode != VISIBILITY_UNSET:
        return (
            source.visibility_mode,
            list(source.visibility_group_ids or []),
            list(source.visibility_user_ids or []),
        )
    return VISIBILITY_ADMINS_ONLY, [], []


def apply_acl_to_evidence_for_document(db: Session, doc: ClientDocument) -> int:
    if not doc.source_id:
        return 0
    q = db.query(EvidenceItem).filter(
        EvidenceItem.organization_id == doc.organization_id,
        EvidenceItem.source_id == doc.source_id,
        EvidenceItem.file_name == doc.file_name,
    )
    count = 0
    for item in q.all():
        item.visibility_mode = doc.visibility_mode
        item.visibility_group_ids = list(doc.visibility_group_ids or [])
        item.visibility_user_ids = list(doc.visibility_user_ids or [])
        count += 1
    db.flush()
    return count

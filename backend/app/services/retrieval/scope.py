"""Evidence scope filters shared by retrieval and chat empty-state checks."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Query, Session

from app.models.enums import EvidenceScope
from app.models.evidence import EvidenceItem


def apply_evidence_scope_filter(query: Query, project_id: UUID | None) -> Query:
    """When project_id is set, limit to that project plus org-scoped items. Otherwise org-wide."""
    if project_id is not None:
        return query.filter(
            or_(
                EvidenceItem.project_id == project_id,
                and_(
                    EvidenceItem.project_id.is_(None),
                    EvidenceItem.scope == EvidenceScope.ORGANIZATION.value,
                ),
            )
        )
    return query


def count_org_evidence_chunks(
    db: Session,
    *,
    organization_id: UUID,
    project_id: UUID | None = None,
) -> int:
    """Count chunks that actually have an embedding in this organization.

    Project scope is ignored: an employee question searches the whole organization.
    """
    del project_id
    q = db.query(func.count(EvidenceItem.id)).filter(
        EvidenceItem.organization_id == organization_id,
        EvidenceItem.embedding.is_not(None),
    )
    return int(q.scalar() or 0)

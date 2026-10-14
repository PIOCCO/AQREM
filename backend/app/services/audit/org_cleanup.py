"""Batch delete org-scoped audit events (tenant database)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.audit.service import record_audit
from app.models.audit import AuditEvent

AUDIT_CLEANUP_ACTION = "audit_logs_cleaned_up"
PROTECTED_ACTIONS = frozenset({AUDIT_CLEANUP_ACTION})

ALLOWED_SCOPES = frozenset({"older_than_7d", "older_than_30d", "all"})

BATCH_SIZE = 1000


def _cutoff_for_scope(scope: str, *, now: datetime | None = None) -> datetime | None:
    now = now or datetime.now(UTC)
    if scope == "older_than_7d":
        return now - timedelta(days=7)
    if scope == "older_than_30d":
        return now - timedelta(days=30)
    return None


def cleanup_org_audit_logs(
    db: Session,
    *,
    organization_id: UUID,
    admin_user_id: UUID,
    scope: str,
) -> int:
    if scope not in ALLOWED_SCOPES:
        raise ValueError("INVALID_SCOPE")

    cutoff = _cutoff_for_scope(scope)
    deleted_total = 0

    while True:
        q = (
            select(AuditEvent.id)
            .where(
                AuditEvent.organization_id == organization_id,
                AuditEvent.action.notin_(PROTECTED_ACTIONS),
            )
            .order_by(AuditEvent.created_at.asc())
            .limit(BATCH_SIZE)
        )
        if cutoff is not None:
            q = q.where(AuditEvent.created_at < cutoff)

        ids = [row[0] for row in db.execute(q).all()]
        if not ids:
            break
        result = db.execute(delete(AuditEvent).where(AuditEvent.id.in_(ids)))
        db.flush()
        deleted_total += int(result.rowcount or 0)

    record_audit(
        db,
        organization_id=organization_id,
        user_id=admin_user_id,
        action=AUDIT_CLEANUP_ACTION,
        resource_type="audit_log",
        resource_id=str(organization_id),
        metadata={"scope": scope, "deleted_count": deleted_total},
    )
    return deleted_total


def purge_audit_logs_older_than_days(
    db: Session,
    *,
    organization_id: UUID,
    days: int,
) -> int:
    """Scheduled retention: delete old logs except protected cleanup records."""
    cutoff = datetime.now(UTC) - timedelta(days=days)
    deleted_total = 0
    while True:
        q = (
            select(AuditEvent.id)
            .where(
                AuditEvent.organization_id == organization_id,
                AuditEvent.action.notin_(PROTECTED_ACTIONS),
                AuditEvent.created_at < cutoff,
            )
            .limit(BATCH_SIZE)
        )
        ids = [row[0] for row in db.execute(q).all()]
        if not ids:
            break
        result = db.execute(delete(AuditEvent).where(AuditEvent.id.in_(ids)))
        db.flush()
        deleted_total += int(result.rowcount or 0)
    return deleted_total

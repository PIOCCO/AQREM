"""Per-user chat attachment upload rate limit."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.audit import AuditEvent
from app.services.uploads.chat_validation import ChatValidationError


def assert_chat_upload_rate(db: Session, *, organization_id: UUID, user_id: UUID) -> None:
    settings = get_settings()
    since = datetime.now(UTC) - timedelta(hours=1)
    count = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.organization_id == organization_id,
            AuditEvent.user_id == user_id,
            AuditEvent.action == "chat_attachment_uploaded",
            AuditEvent.created_at >= since,
        )
        .count()
    )
    if count >= settings.chat_attachment_uploads_per_hour:
        raise ChatValidationError(
            code="RATE_LIMIT",
            message=f"You have reached the chat upload limit ({settings.chat_attachment_uploads_per_hour} files per hour). Try again later or use Documents.",
            http_status=429,
        )

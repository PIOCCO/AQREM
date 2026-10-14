from __future__ import annotations

import logging
import threading
import time
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import SessionLocal
from app.models.email_delivery import EmailDeliveryLog
from app.services.email.brevo import BrevoProvider
from app.services.email.console_provider import ConsoleEmailProvider
from app.services.email.types import OutboundEmail, SendResult

logger = logging.getLogger("aqrem.email")


def resolve_email_provider(settings: Settings | None = None):
    settings = settings or get_settings()
    provider_name = settings.resolved_email_provider
    if provider_name == "brevo":
        return BrevoProvider(settings)
    if provider_name == "console":
        if settings.app_env == "production":
            raise RuntimeError("EMAIL_PROVIDER=console is not allowed in production")
        return ConsoleEmailProvider()
    if provider_name in {"none", "disabled", ""}:
        return None
    raise RuntimeError(f"Unknown EMAIL_PROVIDER: {provider_name!r}")


def email_delivery_configured(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return settings.resolved_email_provider in {"brevo", "console"}


def validate_email_config_at_startup(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    provider = settings.resolved_email_provider
    if settings.app_env == "production":
        if provider == "console":
            raise RuntimeError("EMAIL_PROVIDER=console is forbidden when APP_ENV=production")
        if provider == "brevo" and not (settings.brevo_api_key or "").strip():
            raise RuntimeError("BREVO_API_KEY is required when EMAIL_PROVIDER=brevo in production")
        if provider == "brevo" and not (settings.email_from_address or "").strip():
            raise RuntimeError("EMAIL_FROM_ADDRESS is required when EMAIL_PROVIDER=brevo in production")


def _persist_log(
    db: Session,
    *,
    log_id: UUID,
    result: SendResult,
    provider_name: str,
) -> None:
    row = db.get(EmailDeliveryLog, log_id)
    if row is None:
        return
    if result.ok:
        row.status = "sent"
        row.provider_message_id = result.provider_message_id
        row.error_message = None
    else:
        row.status = "failed"
        row.error_message = (result.error_message or "send failed")[:2000]
    row.provider = provider_name
    db.commit()


def _send_with_retries(provider, message: OutboundEmail, settings: Settings) -> SendResult:
    attempts = max(1, settings.email_send_max_retries + 1)
    delay = settings.email_send_retry_backoff_seconds
    last: SendResult = SendResult(ok=False, error_message="not attempted")
    for attempt in range(attempts):
        last = provider.send(message)
        if last.ok:
            return last
        err = (last.error_message or "").lower()
        if "rejected" in err or "400" in err or "401" in err or "403" in err or "404" in err:
            return last
        if attempt + 1 < attempts:
            time.sleep(delay * (2**attempt))
    return last


def queue_email(db: Session, message: OutboundEmail) -> EmailDeliveryLog:
    settings = get_settings()
    provider_name = settings.resolved_email_provider
    log = EmailDeliveryLog(
        email_type=message.email_type,
        recipient=message.to_email.strip().lower(),
        subject=message.subject[:255],
        status="queued",
        provider=provider_name,
        organization_id=UUID(message.organization_id) if message.organization_id else None,
        resource_id=message.resource_id,
        tags={"tags": message.tags},
    )
    db.add(log)
    db.flush()
    log_id = log.id

    def _worker() -> None:
        worker_db = SessionLocal()
        try:
            provider = resolve_email_provider(settings)
            if provider is None:
                _persist_log(
                    worker_db,
                    log_id=log_id,
                    result=SendResult(ok=False, error_message="Email provider disabled"),
                    provider_name=provider_name,
                )
                return
            result = _send_with_retries(provider, message, settings)
            _persist_log(worker_db, log_id=log_id, result=result, provider_name=provider.name)
        except Exception:
            logger.exception("Background email send failed")
            try:
                _persist_log(
                    worker_db,
                    log_id=log_id,
                    result=SendResult(ok=False, error_message="Internal email worker error"),
                    provider_name=provider_name,
                )
            except Exception:
                worker_db.rollback()
        finally:
            worker_db.close()

    threading.Thread(target=_worker, name=f"email-{message.email_type}", daemon=True).start()
    return log


def latest_delivery_status(
    db: Session,
    *,
    email_type: str,
    resource_id: str | None,
    recipient: str | None = None,
) -> tuple[str | None, str | None]:
    q = db.query(EmailDeliveryLog).filter(EmailDeliveryLog.email_type == email_type)
    if resource_id:
        q = q.filter(EmailDeliveryLog.resource_id == resource_id)
    if recipient:
        q = q.filter(EmailDeliveryLog.recipient == recipient.strip().lower())
    row = q.order_by(EmailDeliveryLog.created_at.desc()).first()
    if row is None:
        return None, None
    return row.status, row.error_message

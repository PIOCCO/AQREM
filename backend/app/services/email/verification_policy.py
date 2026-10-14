"""Verification code policy: expiry, attempts, send rate limits."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.email_delivery import EmailDeliveryLog
from app.services.invitations.tokens import hash_token

VERIFICATION_TTL = timedelta(minutes=10)
MAX_VERIFY_ATTEMPTS = 5
MIN_SECONDS_BETWEEN_SENDS = 60
MAX_SENDS_PER_HOUR = 5


def generate_six_digit_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_verification_code(code: str) -> str:
    return hash_token(code.strip())


def verification_expires_at() -> datetime:
    return datetime.now(timezone.utc) + VERIFICATION_TTL


def assert_can_send_verification_email(db: Session, *, recipient: str, email_type: str) -> None:
    normalized = recipient.strip().lower()
    now = datetime.now(timezone.utc)
    last = (
        db.query(EmailDeliveryLog)
        .filter(
            EmailDeliveryLog.recipient == normalized,
            EmailDeliveryLog.email_type == email_type,
        )
        .order_by(EmailDeliveryLog.created_at.desc())
        .first()
    )
    if last is not None:
        created = last.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if (now - created).total_seconds() < MIN_SECONDS_BETWEEN_SENDS:
            raise ValueError("RATE_LIMIT_SEND")
    hour_ago = now - timedelta(hours=1)
    count = (
        db.query(func.count())
        .select_from(EmailDeliveryLog)
        .filter(
            EmailDeliveryLog.recipient == normalized,
            EmailDeliveryLog.email_type == email_type,
            EmailDeliveryLog.created_at >= hour_ago,
        )
        .scalar()
        or 0
    )
    if count >= MAX_SENDS_PER_HOUR:
        raise ValueError("RATE_LIMIT_HOURLY")

"""Self-service password reset (single-use, time-limited tokens)."""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.organization import User
from app.models.password_reset import PasswordResetToken
from app.services.auth.session_invalidation import invalidate_user_sessions
from app.services.email.delivery import send_password_reset_email

logger = logging.getLogger("aqrem.password_reset")

PASSWORD_RESET_GENERIC_MESSAGE = (
    "If an account exists for that email, we sent a link to reset your password. "
    "Check your inbox or ask your administrator for help."
)


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def request_password_reset(db: Session, *, email: str) -> None:
    settings = get_settings()
    normalized = email.strip().lower()
    user = db.query(User).filter(User.email == normalized, User.is_active.is_(True)).first()
    if user is None or not user.hashed_password:
        return

    raw = secrets.token_urlsafe(32)
    row = PasswordResetToken(
        user_id=user.id,
        token_hash=_hash_token(raw),
        expires_at=datetime.now(UTC) + timedelta(minutes=settings.password_reset_expire_minutes),
    )
    db.add(row)
    db.flush()

    reset_url = f"{settings.app_public_base_url.rstrip('/')}/reset-password?token={raw}"
    send_password_reset_email(db=db, to_email=user.email, reset_url=reset_url, user_id=str(user.id))


def reset_password_with_token(db: Session, *, token: str, new_password: str) -> None:
    if len(new_password) < 8:
        raise ValueError("WEAK_PASSWORD")
    digest = _hash_token(token.strip())
    row = db.query(PasswordResetToken).filter(PasswordResetToken.token_hash == digest).first()
    if row is None or row.used_at is not None:
        raise ValueError("INVALID_TOKEN")
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if expires < datetime.now(UTC):
        raise ValueError("INVALID_TOKEN")

    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise ValueError("INVALID_TOKEN")

    user.hashed_password = hash_password(new_password)
    user.must_change_password = False
    row.used_at = datetime.now(UTC)
    invalidate_user_sessions(db, user)

"""Email verification before accepting an organization admin invitation."""

from __future__ import annotations

import secrets
from datetime import timedelta

from sqlalchemy.orm import Session

from app.models.invitation import UserInvitation
from app.models.organization import Organization
from app.services.email.invitations import send_admin_accept_verification_email
from app.services.invitations.admin_invitation import INVITATION_KIND_ORG_ADMIN, preview_admin_invitation
from app.services.invitations.tokens import hash_token, tokens_equal


def _utcnow():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


def send_admin_accept_verification(
    db: Session,
    *,
    token: str,
    email: str,
) -> tuple[UserInvitation, Organization, str | None]:
    invitation, org = preview_admin_invitation(db, token=token)
    if invitation.invitation_kind != INVITATION_KIND_ORG_ADMIN:
        raise ValueError("VERIFICATION_NOT_REQUIRED")
    normalized = email.strip().lower()
    if normalized != invitation.email.strip().lower():
        raise ValueError("EMAIL_MISMATCH")
    code = f"{secrets.randbelow(1_000_000):06d}"
    invitation.accept_verification_code_hash = hash_token(code)
    invitation.accept_verification_expires_at = _utcnow() + timedelta(minutes=15)
    send_admin_accept_verification_email(
        to_email=invitation.email,
        organization_name=org.name,
        code=code,
    )
    from app.core.config import get_settings

    dev = code if get_settings().app_env != "production" else None
    return invitation, org, dev


def assert_admin_accept_verified(invitation: UserInvitation, *, email: str, verification_code: str) -> None:
    if invitation.invitation_kind != INVITATION_KIND_ORG_ADMIN:
        return
    normalized = email.strip().lower()
    if normalized != invitation.email.strip().lower():
        raise ValueError("EMAIL_MISMATCH")
    if not invitation.accept_verification_code_hash or not invitation.accept_verification_expires_at:
        raise ValueError("VERIFICATION_REQUIRED")
    exp = invitation.accept_verification_expires_at
    if exp.tzinfo is None:
        from datetime import timezone

        exp = exp.replace(tzinfo=timezone.utc)
    if exp < _utcnow():
        raise ValueError("VERIFICATION_EXPIRED")
    if not tokens_equal(invitation.accept_verification_code_hash, verification_code.strip()):
        raise ValueError("VERIFICATION_INVALID")
    invitation.accept_verification_code_hash = None
    invitation.accept_verification_expires_at = None

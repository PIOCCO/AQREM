"""Email verification before accepting an organization admin invitation."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.invitation import UserInvitation
from app.models.organization import Organization
from app.services.email.invitations import send_admin_accept_verification_email
from app.services.email.verification_policy import (
    MAX_VERIFY_ATTEMPTS,
    assert_can_send_verification_email,
    generate_six_digit_code,
    hash_verification_code,
    verification_expires_at,
)
from app.services.invitations.admin_invitation import INVITATION_KIND_ORG_ADMIN, preview_admin_invitation
from app.services.invitations.tokens import tokens_equal
from app.audit.service import record_audit


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
    try:
        assert_can_send_verification_email(
            db, recipient=invitation.email, email_type="admin_verification_code"
        )
    except ValueError as exc:
        if str(exc).startswith("RATE_LIMIT"):
            raise ValueError("RATE_LIMIT") from exc
        raise
    code = generate_six_digit_code()
    invitation.accept_verification_code_hash = hash_verification_code(code)
    invitation.accept_verification_expires_at = verification_expires_at()
    invitation.accept_verification_failed_attempts = 0
    send_admin_accept_verification_email(
        db,
        to_email=invitation.email,
        organization_name=org.name,
        organization_id=str(org.id),
        invitation_id=str(invitation.id),
        code=code,
    )
    record_audit(
        db,
        organization_id=org.id,
        user_id=None,
        action="invitation_verification_code_sent",
        resource_type="invitation",
        resource_id=str(invitation.id),
        metadata={"email": invitation.email},
    )
    from app.core.config import get_settings

    dev = code if get_settings().app_env != "production" and get_settings().resolved_email_provider == "console" else None
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
    attempts = int(getattr(invitation, "accept_verification_failed_attempts", 0) or 0)
    if attempts >= MAX_VERIFY_ATTEMPTS:
        invitation.accept_verification_code_hash = None
        invitation.accept_verification_expires_at = None
        raise ValueError("VERIFICATION_LOCKED")
    if not tokens_equal(invitation.accept_verification_code_hash, verification_code.strip()):
        invitation.accept_verification_failed_attempts = attempts + 1
        if invitation.accept_verification_failed_attempts >= MAX_VERIFY_ATTEMPTS:
            invitation.accept_verification_code_hash = None
            invitation.accept_verification_expires_at = None
        raise ValueError("VERIFICATION_INVALID")
    invitation.accept_verification_code_hash = None
    invitation.accept_verification_expires_at = None
    invitation.accept_verification_failed_attempts = 0

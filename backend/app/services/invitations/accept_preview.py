"""Preview any pending user invitation (admin or member) before accept."""

from __future__ import annotations

from datetime import timezone

from sqlalchemy.orm import Session

from app.models.invitation import UserInvitation
from app.models.organization import Organization
from app.services.invitations.admin_invitation import INVITATION_KIND_ORG_ADMIN
from app.services.invitations.tokens import hash_token


def _utcnow():
    from datetime import datetime

    return datetime.now(timezone.utc)


def preview_accept_invitation(db: Session, *, token: str) -> tuple[UserInvitation, Organization]:
    digest = hash_token(token.strip())
    invitation = db.query(UserInvitation).filter(UserInvitation.token_hash == digest).first()
    if invitation is None:
        raise ValueError("Invalid invitation")
    if invitation.used_at is not None:
        raise ValueError("Invitation already used")
    if invitation.revoked_at is not None:
        raise ValueError("Invitation revoked")
    now = _utcnow()
    exp = invitation.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < now:
        raise ValueError("Invitation expired")
    org = db.get(Organization, invitation.organization_id)
    if org is None or not org.is_active:
        raise ValueError("Organization unavailable")
    if getattr(org, "deleted_at", None) is not None:
        raise ValueError("Organization unavailable")
    return invitation, org


def accept_invitation_requires_verification(invitation: UserInvitation) -> bool:
    return (invitation.invitation_kind or INVITATION_KIND_ORG_ADMIN) == INVITATION_KIND_ORG_ADMIN

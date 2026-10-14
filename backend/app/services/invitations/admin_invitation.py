"""Personal organization admin invitations (platform)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.audit.service import record_audit
from app.core.roles import Role
from app.models.invitation import UserInvitation
from app.models.organization import Organization, OrganizationMembership, User
from app.services.email.invitations import send_admin_invitation_email
from app.services.invitations.invite_urls import build_invite_url, invite_path
from app.services.invitations.token_vault import seal_invitation_token, unseal_invitation_token
from app.services.invitations.tokens import generate_opaque_token, hash_token
from app.services.licensing import LicenseDenied, assert_can_add_seat

INVITATION_KIND_ORG_ADMIN = "org_admin"
DEFAULT_EXPIRY_DAYS = 7


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def invitation_setup_path(raw_token: str) -> str:
    return invite_path("admin", raw_token)


def invitation_setup_url(raw_token: str) -> str:
    return build_invite_url("admin", raw_token)


def assert_can_create_org_admin_invite(db: Session, *, organization_id: UUID) -> None:
    """One org admin slot: no active ORG_ADMIN member and no pending admin invite."""
    admin_member = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.role == Role.ORG_ADMIN.value,
            OrganizationMembership.is_active.is_(True),
        )
        .first()
    )
    if admin_member is not None:
        raise ValueError("ORG_ADMIN_EXISTS")
    now = _utcnow()
    pending = (
        db.query(UserInvitation)
        .filter(
            UserInvitation.organization_id == organization_id,
            UserInvitation.invitation_kind == INVITATION_KIND_ORG_ADMIN,
            UserInvitation.used_at.is_(None),
            UserInvitation.revoked_at.is_(None),
            UserInvitation.expires_at > now,
        )
        .first()
    )
    if pending is not None:
        raise ValueError("ORG_ADMIN_INVITE_PENDING")


def assert_email_available_for_org(db: Session, *, email: str, organization_id: UUID) -> None:
    normalized = email.strip().lower()
    user = db.query(User).filter(User.email == normalized).first()
    if user is None:
        return
    other = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.is_active.is_(True),
            OrganizationMembership.organization_id != organization_id,
        )
        .first()
    )
    if other is not None:
        raise ValueError("EMAIL_IN_OTHER_ORG")


def revoke_active_admin_invitations(
    db: Session,
    *,
    organization_id: UUID,
    admin_user_id: UUID,
    except_invitation_id: UUID | None = None,
) -> None:
    now = _utcnow()
    q = db.query(UserInvitation).filter(
        UserInvitation.organization_id == organization_id,
        UserInvitation.invitation_kind == INVITATION_KIND_ORG_ADMIN,
        UserInvitation.used_at.is_(None),
        UserInvitation.revoked_at.is_(None),
        UserInvitation.expires_at > now,
    )
    if except_invitation_id is not None:
        q = q.filter(UserInvitation.id != except_invitation_id)
    for inv in q.all():
        inv.revoked_at = now
        record_audit(
            db,
            organization_id=organization_id,
            user_id=admin_user_id,
            action="admin_invitation_revoked",
            resource_type="invitation",
            resource_id=str(inv.id),
            metadata={"email": inv.email, "reason": "replaced"},
        )


def provision_admin_invitation(
    db: Session,
    *,
    admin_user_id: UUID,
    organization_id: UUID,
    email: str,
    full_name: str,
    personal_message: str | None = None,
    expires_days: int = DEFAULT_EXPIRY_DAYS,
    invitation_base_path: str = "/accept-invite",
) -> tuple[User, OrganizationMembership, UserInvitation, str, datetime, bool]:
    org = db.get(Organization, organization_id)
    if org is None or not org.is_active:
        raise ValueError("Organization not found or inactive")

    expires_days = max(1, min(14, int(expires_days)))
    normalized_email = email.strip().lower()

    assert_email_available_for_org(db, email=normalized_email, organization_id=organization_id)

    try:
        assert_can_add_seat(db, org)
    except LicenseDenied as exc:
        raise LicenseDenied(exc.detail) from exc

    revoke_active_admin_invitations(db, organization_id=organization_id, admin_user_id=admin_user_id)

    now = _utcnow()
    pending_same = (
        db.query(UserInvitation)
        .filter(
            UserInvitation.organization_id == organization_id,
            UserInvitation.email == normalized_email,
            UserInvitation.used_at.is_(None),
            UserInvitation.revoked_at.is_(None),
            UserInvitation.expires_at > now,
        )
        .first()
    )
    if pending_same:
        raise ValueError("DUPLICATE_EMAIL")

    user = db.query(User).filter(User.email == normalized_email).first()
    if user is None:
        user = User(
            email=normalized_email,
            full_name=full_name,
            hashed_password=None,
            is_active=True,
            must_change_password=True,
        )
        db.add(user)
        db.flush()
    elif not user.is_active:
        raise ValueError("User account is deactivated")
    else:
        user.full_name = full_name or user.full_name

    membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user.id,
        )
        .first()
    )
    if membership is None:
        membership = OrganizationMembership(
            organization_id=organization_id,
            user_id=user.id,
            role=Role.ORG_ADMIN.value,
            is_active=False,
        )
        db.add(membership)
    else:
        membership.role = Role.ORG_ADMIN.value
        membership.is_active = False

    raw_token = generate_opaque_token()
    expires_at = now + timedelta(days=expires_days)
    invitation = UserInvitation(
        organization_id=organization_id,
        email=normalized_email,
        role=Role.ORG_ADMIN.value,
        invitation_kind=INVITATION_KIND_ORG_ADMIN,
        invitee_full_name=full_name,
        personal_message=(personal_message or "")[:2000] or None,
        token_hash=hash_token(raw_token),
        token_ciphertext=seal_invitation_token(raw_token),
        expires_at=expires_at,
        created_by_user_id=admin_user_id,
    )
    db.add(invitation)
    db.flush()

    record_audit(
        db,
        organization_id=organization_id,
        user_id=admin_user_id,
        action="admin_invitation_created",
        resource_type="invitation",
        resource_id=str(invitation.id),
        metadata={"email": normalized_email, "expires_days": expires_days},
    )

    invitation_url = invitation_setup_url(raw_token)
    email_sent = send_admin_invitation_email(
        to_email=normalized_email,
        invitee_name=full_name,
        organization_name=org.name,
        invitation_url=invitation_url,
        personal_message=personal_message,
    )
    return user, membership, invitation, raw_token, expires_at, email_sent


def resend_admin_invitation(
    db: Session,
    *,
    admin_user_id: UUID,
    invitation: UserInvitation,
    expires_days: int = DEFAULT_EXPIRY_DAYS,
) -> tuple[str, datetime]:
    if invitation.invitation_kind != INVITATION_KIND_ORG_ADMIN:
        raise ValueError("Not an admin invitation")
    if invitation.used_at is not None or invitation.revoked_at is not None:
        raise ValueError("Invitation is not pending")
    now = _utcnow()
    last = getattr(invitation, "last_resent_at", None)
    if last is not None:
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if (now - last).total_seconds() < 60:
            raise ValueError("RESEND_RATE_LIMIT")
    if not invitation.token_ciphertext:
        raise ValueError("LINK_UNAVAILABLE")
    raw_token = unseal_invitation_token(invitation.token_ciphertext)
    expires_at = invitation.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    invitation.last_resent_at = now
    record_audit(
        db,
        organization_id=invitation.organization_id,
        user_id=admin_user_id,
        action="admin_invitation_resent",
        resource_type="invitation",
        resource_id=str(invitation.id),
        metadata={"email": invitation.email},
    )
    org = db.get(Organization, invitation.organization_id)
    if org is not None:
        send_admin_invitation_email(
            to_email=invitation.email,
            invitee_name=invitation.invitee_full_name or invitation.email,
            organization_name=org.name,
            invitation_url=invitation_setup_url(raw_token),
            personal_message=invitation.personal_message,
        )
    return raw_token, expires_at


def preview_admin_invitation(db: Session, *, token: str) -> tuple[UserInvitation, Organization]:
    digest = hash_token(token.strip())
    invitation = db.query(UserInvitation).filter(UserInvitation.token_hash == digest).first()
    if invitation is None:
        raise ValueError("Invalid invitation")
    if invitation.invitation_kind != INVITATION_KIND_ORG_ADMIN:
        raise ValueError("Invalid invitation")
    now = _utcnow()
    if invitation.used_at is not None or invitation.revoked_at is not None:
        raise ValueError("Invalid invitation")
    exp = invitation.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < now:
        raise ValueError("Invalid invitation")
    org = db.get(Organization, invitation.organization_id)
    if org is None or not org.is_active:
        raise ValueError("Invalid invitation")
    if getattr(org, "deleted_at", None) is not None:
        raise ValueError("Invalid invitation")
    return invitation, org


def resolve_admin_invitation_link(invitation: UserInvitation) -> str:
    """Return setup path for a pending invite using sealed token."""
    if invitation.used_at is not None:
        raise ValueError("INVITATION_ACCEPTED")
    if not invitation.token_ciphertext:
        raise ValueError("LINK_UNAVAILABLE")
    raw = unseal_invitation_token(invitation.token_ciphertext)
    return invitation_setup_path(raw)


def reissue_admin_invitation(
    db: Session,
    *,
    admin_user_id: UUID,
    invitation: UserInvitation,
    expires_days: int = DEFAULT_EXPIRY_DAYS,
) -> tuple[str, datetime]:
    """New token for expired/revoked pending invites (still unused)."""
    if invitation.invitation_kind != INVITATION_KIND_ORG_ADMIN:
        raise ValueError("Not an admin invitation")
    if invitation.used_at is not None:
        raise ValueError("Invitation already accepted")
    expires_days = max(1, min(14, int(expires_days)))
    raw_token = generate_opaque_token()
    expires_at = _utcnow() + timedelta(days=expires_days)
    invitation.token_hash = hash_token(raw_token)
    invitation.token_ciphertext = seal_invitation_token(raw_token)
    invitation.expires_at = expires_at
    invitation.revoked_at = None
    record_audit(
        db,
        organization_id=invitation.organization_id,
        user_id=admin_user_id,
        action="admin_invitation_reissued",
        resource_type="invitation",
        resource_id=str(invitation.id),
        metadata={"email": invitation.email},
    )
    return raw_token, expires_at


def delete_admin_invitation(
    db: Session,
    *,
    admin_user_id: UUID,
    invitation: UserInvitation,
) -> None:
    """Remove invitation history row; pending invites are revoked first."""
    is_org_admin_invite = invitation.invitation_kind == INVITATION_KIND_ORG_ADMIN or (
        invitation.role == Role.ORG_ADMIN.value
    )
    if not is_org_admin_invite:
        raise ValueError("Not an admin invitation")
    now = _utcnow()
    if invitation.used_at is None and invitation.revoked_at is None:
        invitation.revoked_at = now
    record_audit(
        db,
        organization_id=invitation.organization_id,
        user_id=admin_user_id,
        action="admin_invitation_deleted",
        resource_type="invitation",
        resource_id=str(invitation.id),
        metadata={"email": invitation.email, "was_accepted": invitation.used_at is not None},
    )
    db.delete(invitation)


def invitation_public_status(inv: UserInvitation, *, now: datetime | None = None) -> str:
    now = now or _utcnow()
    if inv.used_at is not None:
        return "accepted"
    if inv.revoked_at is not None:
        return "revoked"
    exp = inv.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < now:
        return "expired"
    return "pending"

"""Platform administrator provisioning (organizations, users, invitations)."""

from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.audit.service import record_audit
from app.core.config import get_settings
from app.core.roles import Role
from app.core.security import hash_password
from app.models.enums import LicenseStatus
from app.models.invitation import UserInvitation
from app.models.organization import Organization, OrganizationMembership, User
from app.services.licensing import LicenseDenied, assert_can_add_seat, licensing_test_mode_effective


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "org"


def unique_org_slug(db: Session, name: str) -> str:
    base = _slugify(name)
    slug = base
    n = 2
    while db.query(Organization).filter(Organization.slug == slug).first():
        slug = f"{base}-{n}"
        n += 1
    return slug


def hash_invitation_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_organization_admin(
    db: Session,
    *,
    admin_user_id: UUID,
    name: str,
    slug: str | None = None,
    license_limit: int = 0,
    license_status: LicenseStatus | None = None,
    owner_display_name: str | None = None,
) -> Organization:
    settings = get_settings()
    status_value = license_status
    if status_value is None:
        status_value = LicenseStatus.TEST if licensing_test_mode_effective(settings) else LicenseStatus.ACTIVE

    org = Organization(
        name=name,
        slug=slug or unique_org_slug(db, name),
        license_limit=license_limit,
        license_status=status_value.value,
        is_active=True,
        owner_display_name=owner_display_name,
    )
    db.add(org)
    db.flush()
    record_audit(
        db,
        organization_id=org.id,
        user_id=admin_user_id,
        action="organization_created",
        resource_type="organization",
        resource_id=str(org.id),
        metadata={"license_limit": license_limit, "license_status": org.license_status},
    )
    return org


def provision_user_invitation(
    db: Session,
    *,
    admin_user_id: UUID,
    organization_id: UUID,
    email: str,
    full_name: str,
    role: Role,
    expires_hours: int = 72,
) -> tuple[User, OrganizationMembership, UserInvitation, str, datetime]:
    org = db.get(Organization, organization_id)
    if org is None or not org.is_active:
        raise ValueError("Organization not found or inactive")

    try:
        assert_can_add_seat(db, org)
    except LicenseDenied as exc:
        raise LicenseDenied(exc.detail) from exc

    now = datetime.now(timezone.utc)
    pending_same = (
        db.query(UserInvitation)
        .filter(
            UserInvitation.organization_id == organization_id,
            UserInvitation.email == email.lower(),
            UserInvitation.used_at.is_(None),
            UserInvitation.revoked_at.is_(None),
            UserInvitation.expires_at > now,
        )
        .first()
    )
    if pending_same:
        raise ValueError("DUPLICATE_EMAIL")

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(
            email=email,
            full_name=full_name,
            hashed_password=None,
            is_active=True,
            must_change_password=True,
        )
        db.add(user)
        db.flush()
    elif not user.is_active:
        raise ValueError("User account is deactivated")

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
            role=role.value,
            is_active=True,
        )
        db.add(membership)
    else:
        membership.role = role.value
        membership.is_active = True

    raw_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_hours)
    invitation = UserInvitation(
        organization_id=organization_id,
        email=email,
        role=role.value,
        invitation_kind="member" if role != Role.ORG_ADMIN else "org_admin",
        token_hash=hash_invitation_token(raw_token),
        expires_at=expires_at,
        created_by_user_id=admin_user_id,
    )
    db.add(invitation)
    db.flush()

    record_audit(
        db,
        organization_id=organization_id,
        user_id=admin_user_id,
        action="user_invited",
        resource_type="user",
        resource_id=str(user.id),
        metadata={"email": email, "role": role.value, "invitation_id": str(invitation.id)},
    )
    if org is not None and invitation.invitation_kind == "member":
        from app.services.email.invitations import send_member_invitation_email
        from app.services.invitations.invite_urls import build_invite_url

        send_member_invitation_email(
            db,
            to_email=email.lower(),
            invitee_name=full_name,
            organization_name=org.name,
            invitation_url=build_invite_url("member", raw_token),
            expires_at=expires_at,
            organization_id=str(organization_id),
            invitation_id=str(invitation.id),
        )
    return user, membership, invitation, raw_token, expires_at


def resend_invitation(
    db: Session,
    *,
    admin_user_id: UUID,
    invitation: UserInvitation,
    expires_hours: int = 72,
) -> tuple[str, datetime]:
    if invitation.used_at is not None or invitation.revoked_at is not None:
        raise ValueError("Invitation is not pending")
    raw_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_hours)
    invitation.token_hash = hash_invitation_token(raw_token)
    invitation.expires_at = expires_at
    record_audit(
        db,
        organization_id=invitation.organization_id,
        user_id=admin_user_id,
        action="invitation_resent",
        resource_type="invitation",
        resource_id=str(invitation.id),
        metadata={"email": invitation.email},
    )
    return raw_token, expires_at


def revoke_pending_invitations_for_email(
    db: Session,
    *,
    admin_user_id: UUID,
    organization_id: UUID,
    email: str,
) -> int:
    """Revoke all pending invitations for an email within an organization."""
    now = datetime.now(timezone.utc)
    normalized = email.strip().lower()
    invites = (
        db.query(UserInvitation)
        .filter(
            UserInvitation.organization_id == organization_id,
            UserInvitation.email == normalized,
            UserInvitation.used_at.is_(None),
            UserInvitation.revoked_at.is_(None),
            UserInvitation.expires_at > now,
        )
        .all()
    )
    for inv in invites:
        revoke_invitation(db, admin_user_id=admin_user_id, invitation=inv)
    return len(invites)


def revoke_invitation(
    db: Session,
    *,
    admin_user_id: UUID,
    invitation: UserInvitation,
) -> None:
    if invitation.used_at is not None:
        raise ValueError("Invitation already accepted")
    invitation.revoked_at = datetime.now(timezone.utc)
    record_audit(
        db,
        organization_id=invitation.organization_id,
        user_id=admin_user_id,
        action="invitation_revoked",
        resource_type="invitation",
        resource_id=str(invitation.id),
        metadata={"email": invitation.email},
    )
    if invitation.used_at is None:
        user = db.query(User).filter(User.email == invitation.email.strip().lower()).first()
        if user is not None:
            membership = (
                db.query(OrganizationMembership)
                .filter(
                    OrganizationMembership.organization_id == invitation.organization_id,
                    OrganizationMembership.user_id == user.id,
                    OrganizationMembership.is_active.is_(True),
                )
                .first()
            )
            if membership is not None:
                from app.services.membership_lifecycle import remove_organization_membership

                remove_organization_membership(
                    db,
                    admin_user_id=admin_user_id,
                    membership=membership,
                    reason="invitation_revoked",
                    source="platform_control_plane",
                    audit_action="platform_member_removed",
                )


def update_membership_role(
    db: Session,
    *,
    admin_user_id: UUID,
    membership: OrganizationMembership,
    role: Role,
) -> None:
    from app.services.membership_lifecycle import normalize_org_admin_singleton

    old = membership.role
    if role == Role.ORG_ADMIN:
        others = (
            db.query(OrganizationMembership)
            .filter(
                OrganizationMembership.organization_id == membership.organization_id,
                OrganizationMembership.role == Role.ORG_ADMIN.value,
                OrganizationMembership.id != membership.id,
                OrganizationMembership.is_active.is_(True),
            )
            .all()
        )
        for other in others:
            other.role = Role.EDITOR.value
            other.auth_version = int(other.auth_version or 1) + 1
    membership.role = role.value
    if role == Role.ORG_ADMIN:
        normalize_org_admin_singleton(db, membership.organization_id)
    record_audit(
        db,
        organization_id=membership.organization_id,
        user_id=admin_user_id,
        action="member_role_changed",
        resource_type="organization_membership",
        resource_id=str(membership.id),
        metadata={"user_id": str(membership.user_id), "from": old, "to": role.value},
    )


def accept_invitation(
    db: Session,
    *,
    token: str,
    email: str,
    verification_code: str,
    password: str,
    full_name: str | None = None,
) -> tuple[User, OrganizationMembership]:
    token_hash = hash_invitation_token(token)
    invitation = db.query(UserInvitation).filter(UserInvitation.token_hash == token_hash).first()
    if invitation is None:
        raise ValueError("Invalid invitation")
    from app.services.invitations.admin_invitation_accept import assert_admin_accept_verified

    assert_admin_accept_verified(invitation, email=email, verification_code=verification_code)
    if invitation.used_at is not None:
        raise ValueError("Invitation already used")
    now = datetime.now(timezone.utc)
    expires = invitation.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < now:
        raise ValueError("Invitation expired")

    user = db.query(User).filter(User.email == invitation.email).first()
    if user is None:
        raise ValueError("User not found for invitation")
    if user.is_platform_admin or (user.platform_role or "").strip():
        raise ValueError("PLATFORM_ACCOUNT")

    user.hashed_password = hash_password(password)
    user.must_change_password = False
    user.is_active = True
    user.email_verified_at = now
    if full_name:
        user.full_name = full_name

    membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == invitation.organization_id,
            OrganizationMembership.user_id == user.id,
        )
        .first()
    )
    if membership is None:
        raise ValueError("Membership missing for invitation")

    membership.is_active = True
    membership.role = invitation.role
    invitation.used_at = now

    record_audit(
        db,
        organization_id=invitation.organization_id,
        user_id=user.id,
        action="invitation_accepted",
        resource_type="user",
        resource_id=str(user.id),
        metadata={"invitation_id": str(invitation.id)},
    )
    return user, membership


def set_organization_license(
    db: Session,
    *,
    admin_user_id: UUID,
    org: Organization,
    license_limit: int | None = None,
    license_status: LicenseStatus | None = None,
    is_active: bool | None = None,
) -> Organization:
    if license_limit is not None:
        org.license_limit = license_limit
    if license_status is not None:
        settings = get_settings()
        if license_status == LicenseStatus.TEST and not licensing_test_mode_effective(settings):
            raise ValueError("Test license status is only allowed when licensing test mode is enabled")
        org.license_status = license_status.value
        if license_status == LicenseStatus.EXPIRED and org.license_expires_at is None:
            org.license_expires_at = datetime.now(timezone.utc)
    if is_active is not None:
        org.is_active = is_active

    record_audit(
        db,
        organization_id=org.id,
        user_id=admin_user_id,
        action="organization_license_updated",
        resource_type="organization",
        resource_id=str(org.id),
        metadata={
            "license_limit": org.license_limit,
            "license_status": org.license_status,
            "is_active": org.is_active,
            "source": "platform_control_plane",
        },
    )
    return org


def deactivate_membership(
    db: Session,
    *,
    admin_user_id: UUID,
    membership: OrganizationMembership,
    reason: str | None = None,
    source: str = "platform_control_plane",
) -> None:
    """Deprecated alias: removes membership from the organization (hard delete)."""
    from app.services.membership_lifecycle import remove_organization_membership

    remove_organization_membership(
        db,
        admin_user_id=admin_user_id,
        membership=membership,
        reason=reason,
        source=source,
        audit_action="platform_member_removed",
    )


def deactivate_user_account(
    db: Session,
    *,
    admin_user_id: UUID,
    user: User,
) -> None:
    if user.is_platform_admin:
        raise ValueError("Cannot deactivate platform administrator")
    user.is_active = False
    for membership in user.memberships:
        membership.is_active = False
        record_audit(
            db,
            organization_id=membership.organization_id,
            user_id=admin_user_id,
            action="user_deactivated",
            resource_type="user",
            resource_id=str(user.id),
            metadata={},
        )

"""Organization-wide employee join links."""

from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.audit.service import record_audit
from app.core.roles import Role
from app.models.employee_join import (
    EmployeeJoinLink,
    EmployeeJoinPending,
    EmployeeJoinVerification,
    OrganizationJoinBlocklist,
)
from app.models.organization import Organization, OrganizationMembership, User
from app.services.email.invitations import send_join_verification_email, send_employee_welcome_email
from app.services.invitations.admin_invitation import assert_email_available_for_org
from app.services.invitations.tokens import generate_opaque_token, hash_token, tokens_equal
from app.services.licensing import LicenseDenied, assert_can_add_seat, org_allows_sign_in
from app.services.access_control.groups import ensure_default_access_groups
from app.models.access_group import AccessGroupMembership
from app.tenant_store.resolver import open_tenant_session

LINK_ACTIVE = "active"
LINK_PAUSED = "paused"
LINK_DISABLED = "disabled"

PENDING_VERIFICATION = "pending_verification"
EMAIL_VERIFIED = "email_verified"
PENDING_APPROVAL = "pending_approval"
PENDING_JOINED = "joined"
PENDING_REJECTED = "rejected"

ABUSE_THRESHOLD = 25
ABUSE_WINDOW_MINUTES = 15

GENERIC_JOIN_ERROR = "This link is not valid. Ask your administrator for a new one."


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_domains(domains: list[str] | None) -> list[str] | None:
    if not domains:
        return None
    out: list[str] = []
    for d in domains:
        part = d.strip().lower().lstrip("@")
        if part and part not in out:
            out.append(part)
    return out or None


def _email_domain(email: str) -> str:
    return email.rsplit("@", 1)[-1].lower()


def get_active_link_for_org(db: Session, organization_id: UUID) -> EmployeeJoinLink | None:
    return (
        db.query(EmployeeJoinLink)
        .filter(
            EmployeeJoinLink.organization_id == organization_id,
            EmployeeJoinLink.status.in_([LINK_ACTIVE, LINK_PAUSED]),
        )
        .order_by(EmployeeJoinLink.created_at.desc())
        .first()
    )


def _link_is_usable(link: EmployeeJoinLink, org: Organization, *, now: datetime | None = None) -> bool:
    now = now or _utcnow()
    if link.status != LINK_ACTIVE:
        return False
    if not org.is_active:
        return False
    allowed, _ = org_allows_sign_in(org)
    if not allowed:
        return False
    if link.expires_at is not None:
        exp = link.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < now:
            return False
    if link.max_joins is not None and link.joined_count + link.pending_approval_count >= link.max_joins:
        return False
    return True


def find_link_by_token(db: Session, token: str) -> tuple[EmployeeJoinLink, Organization] | None:
    digest = hash_token(token.strip())
    link = db.query(EmployeeJoinLink).filter(EmployeeJoinLink.token_hash == digest).first()
    if link is None:
        return None
    org = db.get(Organization, link.organization_id)
    if org is None:
        return None
    return link, org


def create_employee_join_link(
    db: Session,
    *,
    admin_user_id: UUID,
    organization_id: UUID,
    allowed_domains: list[str] | None,
    require_admin_approval: bool,
    max_joins: int | None,
    expires_days: int | None,
) -> tuple[EmployeeJoinLink, str]:
    org = db.get(Organization, organization_id)
    if org is None or not org.is_active:
        raise ValueError("Organization not found")

    domains = _normalize_domains(allowed_domains)
    if domains is None and not require_admin_approval:
        raise ValueError("DOMAINS_OR_APPROVAL_REQUIRED")
    if domains is None:
        require_admin_approval = True

    now = _utcnow()
    existing = get_active_link_for_org(db, organization_id)
    if existing is not None:
        existing.status = LINK_DISABLED
        existing.disabled_at = now

    if max_joins is None:
        from app.services.seat_usage import get_seat_usage

        usage = get_seat_usage(db, org)
        max_joins = max(0, usage.seats_available)

    expires_at = None
    if expires_days is not None and expires_days > 0:
        expires_at = now + timedelta(days=min(90, expires_days))

    raw = generate_opaque_token()
    link = EmployeeJoinLink(
        organization_id=organization_id,
        token_hash=hash_token(raw),
        status=LINK_ACTIVE,
        allowed_domains=domains,
        require_admin_approval=require_admin_approval,
        max_joins=max_joins,
        expires_at=expires_at,
        created_by_user_id=admin_user_id,
    )
    db.add(link)
    db.flush()

    record_audit(
        db,
        organization_id=organization_id,
        user_id=admin_user_id,
        action="employee_link_created",
        resource_type="employee_join_link",
        resource_id=str(link.id),
        metadata={
            "require_admin_approval": require_admin_approval,
            "domain_count": len(domains or []),
            "max_joins": max_joins,
            "expires_days": expires_days,
        },
    )
    return link, raw


def rotate_employee_link(db: Session, *, admin_user_id: UUID, link: EmployeeJoinLink) -> str:
    raw = generate_opaque_token()
    link.token_hash = hash_token(raw)
    link.rotated_at = _utcnow()
    record_audit(
        db,
        organization_id=link.organization_id,
        user_id=admin_user_id,
        action="employee_link_rotated",
        resource_type="employee_join_link",
        resource_id=str(link.id),
        metadata={},
    )
    return raw


def set_link_status(
    db: Session,
    *,
    admin_user_id: UUID,
    link: EmployeeJoinLink,
    status: str,
) -> None:
    if status not in {LINK_ACTIVE, LINK_PAUSED, LINK_DISABLED}:
        raise ValueError("Invalid status")
    link.status = status
    now = _utcnow()
    if status == LINK_DISABLED:
        link.disabled_at = now
    action = "employee_link_paused" if status == LINK_PAUSED else "employee_link_disabled"
    if status == LINK_ACTIVE:
        action = "employee_link_resumed"
    record_audit(
        db,
        organization_id=link.organization_id,
        user_id=admin_user_id,
        action=action,
        resource_type="employee_join_link",
        resource_id=str(link.id),
        metadata={"status": status},
    )


def _record_failed_attempt(db: Session, link: EmployeeJoinLink) -> None:
    now = _utcnow()
    window_start = link.failed_attempts_since
    if window_start is None or (now - window_start).total_seconds() > ABUSE_WINDOW_MINUTES * 60:
        link.failed_attempts_since = now
        link.failed_attempts_window = 1
    else:
        link.failed_attempts_window += 1
    if link.failed_attempts_window >= ABUSE_THRESHOLD and link.status == LINK_ACTIVE:
        link.status = LINK_PAUSED
        record_audit(
            db,
            organization_id=link.organization_id,
            user_id=None,
            action="employee_link_paused",
            resource_type="employee_join_link",
            resource_id=str(link.id),
            metadata={"reason": "abuse_auto_pause"},
        )


def _is_blocked(db: Session, organization_id: UUID, email: str) -> bool:
    return (
        db.query(OrganizationJoinBlocklist)
        .filter(
            OrganizationJoinBlocklist.organization_id == organization_id,
            OrganizationJoinBlocklist.email == email.lower(),
        )
        .first()
        is not None
    )


def join_preview(db: Session, token: str) -> dict[str, str]:
    found = find_link_by_token(db, token)
    if found is None:
        raise ValueError(GENERIC_JOIN_ERROR)
    link, org = found
    if not _link_is_usable(link, org):
        raise ValueError(GENERIC_JOIN_ERROR)
    return {"organization_name": org.name}


def join_start(
    db: Session,
    *,
    token: str,
    email: str,
    full_name: str,
) -> tuple[EmployeeJoinPending, str | None]:
    """Start join — returns pending row and verification code (test/dev only in response)."""
    found = find_link_by_token(db, token)
    if found is None:
        _record_failed_attempt_generic(db)
        raise ValueError(GENERIC_JOIN_ERROR)
    link, org = found
    if not _link_is_usable(link, org):
        _record_failed_attempt(db, link)
        raise ValueError(GENERIC_JOIN_ERROR)

    normalized = email.strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", normalized):
        raise ValueError(GENERIC_JOIN_ERROR)

    if _is_blocked(db, org.id, normalized):
        raise ValueError(GENERIC_JOIN_ERROR)

    try:
        assert_email_available_for_org(db, email=normalized, organization_id=org.id)
    except ValueError:
        raise ValueError(GENERIC_JOIN_ERROR) from None

    if link.allowed_domains:
        if _email_domain(normalized) not in link.allowed_domains:
            raise ValueError(GENERIC_JOIN_ERROR)

    try:
        assert_can_add_seat(db, org)
    except LicenseDenied:
        raise ValueError("This organization has no available seats. Ask your administrator.") from None

    pending = EmployeeJoinPending(
        organization_id=org.id,
        link_id=link.id,
        email=normalized,
        full_name=full_name.strip()[:255],
        status=PENDING_VERIFICATION,
    )
    db.add(pending)
    db.flush()

    code = f"{secrets.randbelow(900000) + 100000:06d}"
    ver = EmployeeJoinVerification(
        pending_id=pending.id,
        code_hash=hash_token(code),
        expires_at=_utcnow() + timedelta(minutes=15),
    )
    db.add(ver)
    send_join_verification_email(to_email=normalized, organization_name=org.name, code=code)

    record_audit(
        db,
        organization_id=org.id,
        user_id=None,
        action="employee_join_started",
        resource_type="employee_join_pending",
        resource_id=str(pending.id),
        metadata={"email": normalized},
    )
    return pending, code


def _record_failed_attempt_generic(db: Session) -> None:
    pass


def join_verify_email(db: Session, *, token: str, pending_id: UUID, code: str) -> EmployeeJoinPending:
    found = find_link_by_token(db, token)
    if found is None:
        raise ValueError(GENERIC_JOIN_ERROR)
    link, org = found
    pending = db.get(EmployeeJoinPending, pending_id)
    if pending is None or pending.link_id != link.id or pending.organization_id != org.id:
        raise ValueError(GENERIC_JOIN_ERROR)
    if pending.status != PENDING_VERIFICATION:
        raise ValueError(GENERIC_JOIN_ERROR)

    ver = (
        db.query(EmployeeJoinVerification)
        .filter(
            EmployeeJoinVerification.pending_id == pending.id,
            EmployeeJoinVerification.used_at.is_(None),
        )
        .order_by(EmployeeJoinVerification.created_at.desc())
        .first()
    )
    if ver is None:
        raise ValueError(GENERIC_JOIN_ERROR)
    exp = ver.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < _utcnow():
        raise ValueError(GENERIC_JOIN_ERROR)
    if not tokens_equal(ver.code_hash, code.strip()):
        _record_failed_attempt(db, link)
        raise ValueError(GENERIC_JOIN_ERROR)

    ver.used_at = _utcnow()
    pending.email_verified_at = _utcnow()
    if link.require_admin_approval:
        pending.status = PENDING_APPROVAL
        link.pending_approval_count += 1
    else:
        pending.status = EMAIL_VERIFIED

    record_audit(
        db,
        organization_id=org.id,
        user_id=None,
        action="employee_join_email_verified",
        resource_type="employee_join_pending",
        resource_id=str(pending.id),
        metadata={"email": pending.email},
    )
    return pending


def join_complete(
    db: Session,
    *,
    token: str,
    pending_id: UUID,
    password: str,
) -> tuple[User, OrganizationMembership, str]:
    """Create account or activate membership. Returns status label."""
    if len(password) < 8:
        raise ValueError(GENERIC_JOIN_ERROR)
    found = find_link_by_token(db, token)
    if found is None:
        raise ValueError(GENERIC_JOIN_ERROR)
    link, org = found
    pending = db.get(EmployeeJoinPending, pending_id)
    if pending is None or pending.link_id != link.id:
        raise ValueError(GENERIC_JOIN_ERROR)
    if pending.email_verified_at is None:
        raise ValueError(GENERIC_JOIN_ERROR)

    if pending.status == PENDING_APPROVAL and pending.user_id is None:
        user, membership = _create_inactive_joiner(db, org, pending, password)
        pending.user_id = user.id
        record_audit(
            db,
            organization_id=org.id,
            user_id=user.id,
            action="employee_join_pending_approval",
            resource_type="employee_join_pending",
            resource_id=str(pending.id),
            metadata={"email": pending.email},
        )
        return user, membership, "pending_approval"

    if pending.status != EMAIL_VERIFIED:
        raise ValueError(GENERIC_JOIN_ERROR)

    return _finalize_join(db, link, org, pending, password)


def _create_inactive_joiner(
    db: Session, org: Organization, pending: EmployeeJoinPending, password: str
) -> tuple[User, OrganizationMembership]:
    from app.core.security import hash_password

    user = db.query(User).filter(User.email == pending.email).first()
    if user is None:
        user = User(
            email=pending.email,
            full_name=pending.full_name,
            hashed_password=hash_password(password),
            is_active=False,
            must_change_password=False,
        )
        db.add(user)
        db.flush()
    else:
        user.hashed_password = hash_password(password)
        user.is_active = False
    membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == org.id,
            OrganizationMembership.user_id == user.id,
        )
        .first()
    )
    if membership is None:
        membership = OrganizationMembership(
            organization_id=org.id,
            user_id=user.id,
            role=Role.VIEWER.value,
            is_active=False,
        )
        db.add(membership)
    return user, membership


def _finalize_join(
    db: Session,
    link: EmployeeJoinLink,
    org: Organization,
    pending: EmployeeJoinPending,
    password: str,
) -> tuple[User, OrganizationMembership, str]:
    from app.core.security import hash_password

    user = db.query(User).filter(User.email == pending.email).first()
    if user is None:
        user = User(
            email=pending.email,
            full_name=pending.full_name,
            hashed_password=hash_password(password),
            is_active=True,
            must_change_password=False,
        )
        db.add(user)
        db.flush()
    else:
        if user.hashed_password is None:
            user.hashed_password = hash_password(password)
        user.is_active = True
        user.full_name = pending.full_name or user.full_name

    membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == org.id,
            OrganizationMembership.user_id == user.id,
        )
        .first()
    )
    if membership is None:
        membership = OrganizationMembership(
            organization_id=org.id,
            user_id=user.id,
            role=Role.VIEWER.value,
            is_active=True,
        )
        db.add(membership)
    else:
        membership.role = Role.VIEWER.value
        membership.is_active = True

    pending.status = PENDING_JOINED
    pending.user_id = user.id
    if link.pending_approval_count > 0 and link.require_admin_approval:
        link.pending_approval_count = max(0, link.pending_approval_count - 1)
    link.joined_count += 1

    _assign_all_staff_group(db, org.id, user.id)

    send_employee_welcome_email(to_email=user.email, organization_name=org.name)
    record_audit(
        db,
        organization_id=org.id,
        user_id=user.id,
        action="employee_joined",
        resource_type="user",
        resource_id=str(user.id),
        metadata={"email": user.email},
    )
    return user, membership, "joined"


def _assign_all_staff_group(control_db: Session, organization_id: UUID, user_id: UUID) -> None:
    from app.models.access_group import AccessGroup

    tenant_db = open_tenant_session(control_db, organization_id)
    try:
        groups = ensure_default_access_groups(tenant_db, organization_id)
        all_staff = next((g for g in groups if g.slug == "all-staff"), None)
        if all_staff is None:
            all_staff = (
                tenant_db.query(AccessGroup)
                .filter(AccessGroup.organization_id == organization_id, AccessGroup.slug == "all-staff")
                .first()
            )
        if all_staff is not None:
            exists = (
                tenant_db.query(AccessGroupMembership)
                .filter(
                    AccessGroupMembership.group_id == all_staff.id,
                    AccessGroupMembership.user_id == user_id,
                )
                .first()
            )
            if exists is None:
                tenant_db.add(
                    AccessGroupMembership(
                        organization_id=organization_id,
                        group_id=all_staff.id,
                        user_id=user_id,
                    )
                )
        tenant_db.commit()
    finally:
        tenant_db.close()


def approve_pending_join(
    db: Session,
    *,
    approver_user_id: UUID,
    organization_id: UUID,
    pending_id: UUID,
) -> None:
    pending = db.get(EmployeeJoinPending, pending_id)
    if pending is None or pending.organization_id != organization_id:
        raise ValueError("Not found")
    if pending.status != PENDING_APPROVAL or pending.email_verified_at is None:
        raise ValueError("Not pending")
    link = db.get(EmployeeJoinLink, pending.link_id)
    org = db.get(Organization, organization_id)
    if link is None or org is None:
        raise ValueError("Not found")
    user = db.get(User, pending.user_id) if pending.user_id else None
    if user is None:
        raise ValueError("User missing")
    user.is_active = True
    membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user.id,
        )
        .first()
    )
    if membership is None:
        raise ValueError("Membership missing")
    membership.is_active = True
    membership.role = Role.VIEWER.value
    pending.status = PENDING_JOINED
    pending.decided_at = _utcnow()
    pending.decided_by_user_id = approver_user_id
    link.pending_approval_count = max(0, link.pending_approval_count - 1)
    link.joined_count += 1
    _assign_all_staff_group(db, organization_id, user.id)
    send_employee_welcome_email(to_email=user.email, organization_name=org.name)
    record_audit(
        db,
        organization_id=organization_id,
        user_id=approver_user_id,
        action="employee_join_approved",
        resource_type="employee_join_pending",
        resource_id=str(pending.id),
        metadata={"email": pending.email},
    )


def reject_pending_join(
    db: Session,
    *,
    approver_user_id: UUID,
    organization_id: UUID,
    pending_id: UUID,
    reason: str | None = None,
) -> None:
    pending = db.get(EmployeeJoinPending, pending_id)
    if pending is None or pending.organization_id != organization_id:
        raise ValueError("Not found")
    pending.status = PENDING_REJECTED
    pending.decided_at = _utcnow()
    pending.decided_by_user_id = approver_user_id
    link = db.get(EmployeeJoinLink, pending.link_id)
    if link:
        link.pending_approval_count = max(0, link.pending_approval_count - 1)
    db.add(
        OrganizationJoinBlocklist(
            organization_id=organization_id,
            email=pending.email.lower(),
            reason=reason or "rejected",
        )
    )
    record_audit(
        db,
        organization_id=organization_id,
        user_id=approver_user_id,
        action="employee_join_rejected",
        resource_type="employee_join_pending",
        resource_id=str(pending.id),
        metadata={"email": pending.email},
    )

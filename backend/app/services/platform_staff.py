"""Platform staff lifecycle (roles, safety rules)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.audit.service import record_audit
from app.core.platform_access import bump_platform_auth_version, resolve_platform_role
from app.core.platform_roles import PlatformRole
from app.core.security import hash_password
from app.models.organization import User


class PlatformStaffError(ValueError):
    pass


def count_active_super_admins(db: Session) -> int:
    q = db.query(User).filter(User.is_active.is_(True))
    count = 0
    for user in q:
        if resolve_platform_role(user) == PlatformRole.SUPER_ADMIN:
            count += 1
    return count


def assert_can_change_platform_role(
    db: Session,
    *,
    actor: User,
    target: User,
    new_role: PlatformRole | None,
) -> None:
    if actor.id == target.id:
        raise PlatformStaffError("SELF_CHANGE_FORBIDDEN")
    actor_role = resolve_platform_role(actor)
    if actor_role != PlatformRole.SUPER_ADMIN:
        raise PlatformStaffError("INSUFFICIENT_AUTHORITY")
    target_role = resolve_platform_role(target)
    if target_role == PlatformRole.SUPER_ADMIN and new_role != PlatformRole.SUPER_ADMIN:
        if count_active_super_admins(db) <= 1:
            raise PlatformStaffError("LAST_SUPER_ADMIN")


def set_platform_role(
    db: Session,
    *,
    actor_id: UUID,
    target: User,
    role: PlatformRole | None,
    reason: str,
) -> None:
    actor = db.get(User, actor_id)
    if actor is None:
        raise PlatformStaffError("ACTOR_NOT_FOUND")
    assert_can_change_platform_role(db, actor=actor, target=target, new_role=role)
    previous = resolve_platform_role(target)
    target.platform_role = role.value if role else None
    target.is_platform_admin = role == PlatformRole.SUPER_ADMIN
    bump_platform_auth_version(db, target)
    record_audit(
        db,
        organization_id=None,
        user_id=actor_id,
        action="platform_role_changed",
        resource_type="platform_user",
        resource_id=str(target.id),
        metadata={
            "target_email": target.email,
            "previous_role": previous.value if previous else None,
            "new_role": role.value if role else None,
            "reason": reason,
            "source": "platform_control_plane",
        },
    )


def remove_platform_staff(
    db: Session,
    *,
    actor_id: UUID,
    target: User,
    reason: str,
) -> None:
    actor = db.get(User, actor_id)
    if actor is None or resolve_platform_role(actor) != PlatformRole.SUPER_ADMIN:
        raise PlatformStaffError("INSUFFICIENT_AUTHORITY")
    target_role = resolve_platform_role(target)
    if target_role is None:
        raise PlatformStaffError("NOT_PLATFORM_STAFF")
    if target_role == PlatformRole.SUPER_ADMIN:
        if count_active_super_admins(db) <= 1:
            raise PlatformStaffError("LAST_SUPER_ADMIN")
    target.is_active = False
    target.platform_role = None
    target.is_platform_admin = False
    bump_platform_auth_version(db, target)
    record_audit(
        db,
        organization_id=None,
        user_id=actor_id,
        action="platform_staff_removed",
        resource_type="platform_user",
        resource_id=str(target.id),
        metadata={"target_email": target.email, "reason": reason, "source": "platform_control_plane"},
    )


def invite_platform_staff(
    db: Session,
    *,
    actor_id: UUID,
    email: str,
    full_name: str,
    role: PlatformRole,
    temp_password: str,
) -> User:
    actor = db.get(User, actor_id)
    if actor is None or resolve_platform_role(actor) != PlatformRole.SUPER_ADMIN:
        raise PlatformStaffError("INSUFFICIENT_AUTHORITY")
    if role == PlatformRole.SUPER_ADMIN:
        raise PlatformStaffError("SUPER_ADMIN_REQUIRES_APPROVAL")
    existing = db.query(User).filter(User.email == email.lower()).first()
    if existing and resolve_platform_role(existing):
        raise PlatformStaffError("DUPLICATE_PLATFORM_STAFF")
    if existing:
        user = existing
    else:
        user = User(
            email=email.lower(),
            full_name=full_name,
            hashed_password=hash_password(temp_password),
            is_active=True,
            must_change_password=True,
        )
        db.add(user)
        db.flush()
    user.platform_role = role.value
    user.is_platform_admin = False
    bump_platform_auth_version(db, user)
    record_audit(
        db,
        organization_id=None,
        user_id=actor_id,
        action="platform_staff_invited",
        resource_type="platform_user",
        resource_id=str(user.id),
        metadata={"email": user.email, "role": role.value, "source": "platform_control_plane"},
    )
    return user

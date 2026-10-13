"""Read-only audit of live role data against permissions.yaml."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.permissions_catalog import all_organization_role_names, load_catalog
from app.core.platform_access import resolve_platform_role
from app.core.platform_roles import PlatformRole
from app.core.roles import Role
from app.models.organization import Organization, OrganizationMembership, User


def run_roles_audit(db: Session) -> dict:
    issues: list[dict] = []
    known_org_roles = all_organization_role_names()
    known_platform = set((load_catalog().get("platform_roles") or {}).keys())

    super_admins = 0
    for user in db.query(User).all():
        pr = resolve_platform_role(user)
        if pr == PlatformRole.SUPER_ADMIN and user.is_active:
            super_admins += 1
        if user.platform_role and user.platform_role not in known_platform:
            issues.append({"kind": "unknown_platform_role", "user_id": str(user.id), "value": user.platform_role})
        if user.is_platform_admin and pr is None:
            issues.append({"kind": "legacy_platform_flag_without_role", "user_id": str(user.id)})

    for membership in db.query(OrganizationMembership).all():
        if membership.role not in known_org_roles:
            issues.append(
                {
                    "kind": "unknown_org_role",
                    "membership_id": str(membership.id),
                    "role": membership.role,
                }
            )
        user = db.get(User, membership.user_id)
        if user and resolve_platform_role(user) and membership.is_active:
            issues.append(
                {
                    "kind": "platform_role_with_active_tenant_membership",
                    "user_id": str(user.id),
                    "organization_id": str(membership.organization_id),
                }
            )

    for org in db.query(Organization).filter(Organization.is_active.is_(True)).all():
        admins = (
            db.query(OrganizationMembership)
            .filter(
                OrganizationMembership.organization_id == org.id,
                OrganizationMembership.role == Role.ORG_ADMIN.value,
                OrganizationMembership.is_active.is_(True),
            )
            .count()
        )
        if admins == 0:
            issues.append({"kind": "organization_without_org_admin", "organization_id": str(org.id), "name": org.name})

    if super_admins > 5:
        issues.append({"kind": "elevated_super_admin_count", "count": super_admins})

    summary = {}
    for item in issues:
        kind = item["kind"]
        summary[kind] = summary.get(kind, 0) + 1
    summary["active_super_admins"] = super_admins

    return {"issues": issues, "summary": summary}

#!/usr/bin/env python3
"""
One-off cleanup for stale delete/remove state (dry-run by default).

Usage:
  cd backend && python ../scripts/cleanup_delete_inconsistencies.py --dry-run
  cd backend && python ../scripts/cleanup_delete_inconsistencies.py --apply

Before querying, the script runs the same idempotent schema patches as API startup
(ADD COLUMN IF NOT EXISTS for deleted_at, license_expires_at, etc.). Use
--skip-schema-patches only if you already patched the database.

Actions when --apply:
  1. Hard-delete organization_memberships with is_active=false (legacy soft-remove).
  2. Normalize duplicate ORG_ADMIN rows per org (keep newest active, delete inactive dupes).
  3. Optionally schedule soft-delete for orgs by name (--schedule-deletion-name NAME, repeatable).
  4. Revoke pending invitations whose email already has an active membership in the same org.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.roles import Role
from app.db.schema_patches import apply_schema_patches
from app.db.session import SessionLocal, engine
from app.models.invitation import UserInvitation
from app.models.organization import Organization, OrganizationMembership, User
from app.services.membership_lifecycle import normalize_org_admin_singleton, purge_legacy_inactive_memberships
from app.services.org_lifecycle import schedule_organization_deletion
from datetime import datetime, timezone

from app.services.platform_provisioning import revoke_invitation


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Clean up inconsistent delete/remove data")
    p.add_argument("--dry-run", action="store_true", help="Report only (default)")
    p.add_argument("--apply", action="store_true", help="Persist changes")
    p.add_argument(
        "--schedule-deletion-name",
        action="append",
        default=[],
        help="Exact organization name to mark pending_deletion (repeatable)",
    )
    p.add_argument(
        "--skip-schema-patches",
        action="store_true",
        help="Do not run apply_schema_patches before cleanup (DB must already match models)",
    )
    return p.parse_args()


def ensure_database_schema(*, skip: bool) -> None:
    if skip:
        return
    with engine.begin() as conn:
        apply_schema_patches(conn)


def main() -> int:
    args = _parse_args()
    apply = args.apply and not args.dry_run
    if not apply:
        print("DRY RUN — pass --apply to persist changes\n")

    if not args.skip_schema_patches:
        print("Applying idempotent schema patches (same as API startup)...")
        ensure_database_schema(skip=False)
        print()

    with SessionLocal() as db:
        report = run_cleanup(
            db,
            apply=apply,
            schedule_names=[n.strip() for n in args.schedule_deletion_name if n.strip()],
        )
        if apply:
            db.commit()
        else:
            db.rollback()

    for line in report:
        print(line)
    return 0


def run_cleanup(db: Session, *, apply: bool, schedule_names: list[str]) -> list[str]:
    lines: list[str] = []
    orgs = db.query(Organization).all()
    lines.append(f"Organizations total: {len(orgs)}")

    inactive_memberships = (
        db.query(OrganizationMembership)
        .filter(OrganizationMembership.is_active.is_(False))
        .count()
    )
    lines.append(f"Legacy inactive memberships: {inactive_memberships}")

    for org in orgs:
        if apply:
            purged = purge_legacy_inactive_memberships(db, org.id)
            normalize_org_admin_singleton(db, org.id)
        else:
            purged = (
                db.query(OrganizationMembership)
                .filter(
                    OrganizationMembership.organization_id == org.id,
                    OrganizationMembership.is_active.is_(False),
                )
                .count()
            )
        if purged:
            lines.append(f"  org {org.name} ({org.id}): would purge {purged} inactive membership row(s)")

    stale_invites = 0
    for org in orgs:
        active_emails = {
            u.email.strip().lower()
            for u in db.query(User)
            .join(OrganizationMembership, OrganizationMembership.user_id == User.id)
            .filter(
                OrganizationMembership.organization_id == org.id,
                OrganizationMembership.is_active.is_(True),
            )
            .all()
            if u.email
        }
        invites = (
            db.query(UserInvitation)
            .filter(
                UserInvitation.organization_id == org.id,
                UserInvitation.used_at.is_(None),
                UserInvitation.revoked_at.is_(None),
            )
            .all()
        )
        for inv in invites:
            if inv.email.strip().lower() in active_emails:
                stale_invites += 1
                lines.append(f"  stale invite {inv.email} in org {org.name} ({inv.id})")
                if apply:
                    revoke_invitation(
                        db,
                        admin_user_id=inv.created_by_user_id,
                        invitation=inv,
                        cleanup_provisioned_membership=False,
                    )

    lines.append(f"Stale pending invites (email already member): {stale_invites}")

    super_admin = db.query(User).filter(User.is_platform_admin.is_(True)).first()
    if not super_admin:
        lines.append("WARNING: no platform admin user found; cannot schedule org deletions")
        schedule_names = []

    for name in schedule_names:
        org = db.query(Organization).filter(Organization.name == name).first()
        if org is None:
            lines.append(f"  schedule-deletion: org not found for name {name!r}")
            continue
        if org.deleted_at is not None:
            lines.append(f"  schedule-deletion: {name!r} already pending (deleted_at set)")
            continue
        lines.append(f"  schedule-deletion: will mark {name!r} ({org.id}) pending_deletion")
        if apply and super_admin:
            schedule_organization_deletion(
                db,
                admin=super_admin,
                org=org,
                confirm_name=org.name,
            )

    dup_admins = (
        db.query(OrganizationMembership.organization_id)
        .filter(OrganizationMembership.role == Role.ORG_ADMIN.value)
        .group_by(OrganizationMembership.organization_id)
        .having(func.count(OrganizationMembership.id) > 1)
        .count()
    )
    lines.append(f"Organizations with multiple ORG_ADMIN membership rows: {dup_admins}")
    return lines


if __name__ == "__main__":
    raise SystemExit(main())

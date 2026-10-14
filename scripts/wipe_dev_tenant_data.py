#!/usr/bin/env python3
"""
Remove all tenant organizations and related rows from a DEVELOPMENT database.

Keeps platform administrator user accounts (is_platform_admin=true). Does not drop schema.

Usage:
  cd backend && python ../scripts/wipe_dev_tenant_data.py --dry-run
  cd backend && python ../scripts/wipe_dev_tenant_data.py --apply

Before --apply, take a backup:
  pg_dump "$DATABASE_URL" -Fc -f aqrem-dev-backup.dump
Restore:
  pg_restore -d "$DATABASE_URL" --clean --if-exists aqrem-dev-backup.dump
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.schema_patches import apply_schema_patches
from app.db.session import SessionLocal, engine
from app.models.audit import AuditEvent
from app.models.employee_join import EmployeeJoinLink, EmployeeJoinPending
from app.models.invitation import UserInvitation
from app.models.organization import Organization, OrganizationMembership, User
from app.services.org_lifecycle import purge_organization_tenant_data


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Wipe tenant data from dev database (keeps platform admins)")
    p.add_argument("--dry-run", action="store_true", help="Print counts only (default)")
    p.add_argument("--apply", action="store_true", help="Delete data in a transaction")
    p.add_argument(
        "--allow-production-url",
        action="store_true",
        help="Required if DATABASE_URL hostname looks non-local (still blocked when APP_ENV=production)",
    )
    return p.parse_args()


def _mask_database_url(url: str) -> str:
    try:
        parsed = urlparse(url.replace("postgresql+psycopg://", "postgresql://", 1))
        host = parsed.hostname or "?"
        port = parsed.port or 5432
        db = (parsed.path or "").lstrip("/") or "?"
        user = parsed.username or "?"
        return f"postgresql://{user}:***@{host}:{port}/{db}"
    except Exception:
        return "(unparseable DATABASE_URL)"


def _assert_safe_to_run(*, allow_production_url: bool) -> None:
    settings = get_settings()
    url = settings.database_url
    print(f"APP_ENV={settings.app_env}")
    print(f"DATABASE_URL={_mask_database_url(url)}")

    if settings.app_env.strip().lower() == "production":
        raise SystemExit("Refusing to run: APP_ENV=production")

    host = urlparse(url.replace("postgresql+psycopg://", "postgresql://", 1)).hostname or ""
    local_hosts = {"localhost", "127.0.0.1", "postgres", "db", "0.0.0.0"}
    looks_local = host in local_hosts or host.endswith(".local")
    if not looks_local and not allow_production_url:
        raise SystemExit(
            f"Refusing to run: database host {host!r} does not look local. "
            "Take a backup and pass --allow-production-url only if you are certain this is dev."
        )

    prod_hint = re.compile(r"(prod|production|live|azure)", re.I)
    if prod_hint.search(url) and not allow_production_url:
        raise SystemExit("Refusing to run: DATABASE_URL looks like production. Pass --allow-production-url to override.")


def _counts(db: Session) -> dict[str, int]:
    return {
        "organizations": db.scalar(select(func.count()).select_from(Organization)) or 0,
        "memberships": db.scalar(select(func.count()).select_from(OrganizationMembership)) or 0,
        "invitations": db.scalar(select(func.count()).select_from(UserInvitation)) or 0,
        "employee_join_links": db.scalar(select(func.count()).select_from(EmployeeJoinLink)) or 0,
        "employee_join_pending": db.scalar(select(func.count()).select_from(EmployeeJoinPending)) or 0,
        "tenant_users": db.scalar(
            select(func.count()).select_from(User).where(User.is_platform_admin.is_(False))
        )
        or 0,
        "platform_admins": db.scalar(
            select(func.count()).select_from(User).where(User.is_platform_admin.is_(True))
        )
        or 0,
        "audit_events_with_org": db.scalar(
            select(func.count()).select_from(AuditEvent).where(AuditEvent.organization_id.isnot(None))
        )
        or 0,
    }


def _wipe(db: Session) -> None:
    org_ids = [row[0] for row in db.execute(select(Organization.id)).all()]
    for org_id in org_ids:
        purge_organization_tenant_data(db, org_id)

    db.query(AuditEvent).filter(AuditEvent.organization_id.isnot(None)).delete(synchronize_session=False)
    db.query(EmployeeJoinPending).delete(synchronize_session=False)
    db.query(EmployeeJoinLink).delete(synchronize_session=False)
    db.query(UserInvitation).delete(synchronize_session=False)
    db.query(OrganizationMembership).delete(synchronize_session=False)
    db.query(Organization).delete(synchronize_session=False)
    db.query(User).filter(User.is_platform_admin.is_(False)).delete(synchronize_session=False)
    db.flush()


def main() -> int:
    args = _parse_args()
    apply = args.apply and not args.dry_run
    _assert_safe_to_run(allow_production_url=args.allow_production_url)

    with engine.begin() as conn:
        apply_schema_patches(conn)

    print("DRY RUN — pass --apply to delete\n" if not apply else "APPLY — deleting tenant data\n")

    with SessionLocal() as db:
        before = _counts(db)
        print("Before:", before)
        if apply:
            _wipe(db)
            db.commit()
            after = _counts(db)
            print("After:", after)
        else:
            print("After: (unchanged — dry run)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

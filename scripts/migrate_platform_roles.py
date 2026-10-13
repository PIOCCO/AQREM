#!/usr/bin/env python3
"""Map legacy is_platform_admin users to platform_role=SUPER_ADMIN (dry-run by default)."""

from __future__ import annotations

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Persist changes (default is dry-run)")
    args = parser.parse_args()

    from sqlalchemy import select

    from app.core.platform_roles import PlatformRole
    from app.db.session import SessionLocal
    from app.models.organization import User

    with SessionLocal() as db:
        users = db.execute(select(User).where(User.is_platform_admin.is_(True))).scalars().all()
        planned = []
        for user in users:
            if user.platform_role != PlatformRole.SUPER_ADMIN.value:
                planned.append({"email": user.email, "from": user.platform_role, "to": PlatformRole.SUPER_ADMIN.value})
                if args.apply:
                    user.platform_role = PlatformRole.SUPER_ADMIN.value
        if args.apply:
            db.commit()
        print(f"{'Applied' if args.apply else 'Dry-run'}: {len(planned)} user(s)")
        for row in planned:
            print(row)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, "backend")
    raise SystemExit(main())

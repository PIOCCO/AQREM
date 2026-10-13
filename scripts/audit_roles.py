#!/usr/bin/env python3
"""Read-only role model audit against permissions.yaml (dry-run safe)."""

from __future__ import annotations

import json
import sys

from app.db.session import SessionLocal
from app.services.roles_audit import run_roles_audit


def main() -> int:
    with SessionLocal() as db:
        report = run_roles_audit(db)
    print(json.dumps(report, indent=2))
    return 1 if report["issues"] else 0


if __name__ == "__main__":
    sys.path.insert(0, "backend")
    raise SystemExit(main())

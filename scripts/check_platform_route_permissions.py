#!/usr/bin/env python3
"""CI guard: every declared platform endpoint permission must exist in permissions.yaml."""

from __future__ import annotations

import sys

from app.core.permissions_catalog import all_platform_permission_names, platform_endpoint_permissions


def main() -> int:
    endpoints = platform_endpoint_permissions()
    known = all_platform_permission_names()
    missing = sorted({perm for perm in endpoints.values() if perm not in known})
    if missing:
        print("Unknown permissions referenced by platform_endpoints:", missing)
        return 1
    if not endpoints:
        print("No platform_endpoints declared")
        return 1
    print(f"OK: {len(endpoints)} platform endpoints, {len(known)} permission names")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, "backend")
    raise SystemExit(main())

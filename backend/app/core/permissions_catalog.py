"""Load permissions.yaml — single source of truth for role → permission mappings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.core.platform_roles import PlatformRole
from app.core.roles import Role

_CATALOG_PATH = Path(__file__).with_name("permissions.yaml")


@lru_cache
def load_catalog() -> dict[str, Any]:
    with _CATALOG_PATH.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError("permissions.yaml must be a mapping")
    return data


def platform_permissions_for_role(role: PlatformRole | None) -> frozenset[str]:
    if role is None:
        return frozenset()
    catalog = load_catalog()
    raw = catalog.get("platform_roles") or {}
    perms = raw.get(role.value) or []
    return frozenset(str(p) for p in perms)


def organization_permissions_for_role(role: Role | None) -> list[str]:
    if role is None:
        return []
    catalog = load_catalog()
    raw = catalog.get("organization_roles") or {}
    return list(raw.get(role.value) or [])


def platform_endpoint_permissions() -> dict[str, str]:
    catalog = load_catalog()
    raw = catalog.get("platform_endpoints") or {}
    return {str(k): str(v) for k, v in raw.items()}


def platform_permission_matrix() -> dict[str, dict[str, bool]]:
    endpoints = platform_endpoint_permissions()
    catalog = load_catalog()
    roles_raw = catalog.get("platform_roles") or {}
    matrix: dict[str, dict[str, bool]] = {}
    for role_name in roles_raw:
        role = PlatformRole(role_name)
        granted = platform_permissions_for_role(role)
        matrix[role_name] = {perm: perm in granted for perm in sorted(set(endpoints.values()))}
    return matrix


def all_platform_permission_names() -> frozenset[str]:
    catalog = load_catalog()
    names: set[str] = set()
    for perms in (catalog.get("platform_roles") or {}).values():
        names.update(str(p) for p in perms)
    return frozenset(names)


def all_organization_role_names() -> frozenset[str]:
    catalog = load_catalog()
    return frozenset(str(r) for r in (catalog.get("organization_roles") or {}).keys())


def has_platform_permission(role: PlatformRole | None, permission: str) -> bool:
    return permission in platform_permissions_for_role(role)

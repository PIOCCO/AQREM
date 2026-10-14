"""Build public invitation URLs from configured PUBLIC_APP_URL (never from Host header)."""

from __future__ import annotations

import logging
from typing import Literal
from urllib.parse import quote

from app.core.config import get_settings

logger = logging.getLogger("aqrem.invites")

InviteKind = Literal["admin", "employee", "member"]


def public_app_base_url() -> str:
    settings = get_settings()
    raw = (settings.app_public_base_url or "").strip()
    if not raw:
        logger.error("PUBLIC_APP_URL (APP_PUBLIC_BASE_URL) is not configured; invitation URLs cannot be built")
        return ""
    return raw.rstrip("/")


def invite_path(kind: InviteKind, token: str) -> str:
    """Relative path for the SPA router (dedicated route per invitation type)."""
    safe = quote(token.strip(), safe="")
    if kind == "admin":
        return f"/invite/admin/{safe}"
    if kind == "member":
        return f"/invite/member/{safe}"
    return f"/join/{safe}"


def build_invite_url(kind: InviteKind, token: str) -> str:
    base = public_app_base_url()
    if not base:
        raise ValueError("PUBLIC_APP_URL not configured")
    return f"{base}{invite_path(kind, token)}"


def try_build_invite_url(kind: InviteKind, token: str) -> str | None:
    try:
        return build_invite_url(kind, token)
    except ValueError:
        return None


def absolute_from_invite_path(path: str) -> str | None:
    base = public_app_base_url()
    if not base or not path:
        return None
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base}{path}"

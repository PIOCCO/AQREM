"""Build public invitation URLs from PUBLIC_BASE_URL / PUBLIC_APP_URL, with optional request fallback."""

from __future__ import annotations

import logging
from typing import Literal

from starlette.requests import Request
from urllib.parse import quote

from app.core.config import get_settings

logger = logging.getLogger("aqrem.invites")

InviteKind = Literal["admin", "employee", "member"]

_warned_request_fallback = False


def public_app_base_url() -> str:
    """Configured public base URL from environment (empty if unset)."""
    settings = get_settings()
    raw = (settings.app_public_base_url or "").strip()
    return raw.rstrip("/") if raw else ""


def base_url_from_request(request: Request) -> str | None:
    forwarded_proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip()
    forwarded_host = (request.headers.get("x-forwarded-host") or "").split(",")[0].strip()
    host = forwarded_host or (request.headers.get("host") or "").split(",")[0].strip()
    if not host:
        return None
    scheme = forwarded_proto or request.url.scheme or "http"
    return f"{scheme}://{host}".rstrip("/")


def resolve_public_base_url(*, request: Request | None = None) -> str:
    global _warned_request_fallback
    configured = public_app_base_url()
    if configured:
        return configured
    if request is not None:
        derived = base_url_from_request(request)
        if derived:
            if not _warned_request_fallback:
                logger.warning(
                    "PUBLIC_BASE_URL / PUBLIC_APP_URL is not set; deriving invitation base URL from "
                    "Host / X-Forwarded-Host and X-Forwarded-Proto on the incoming request",
                )
                _warned_request_fallback = True
            return derived
    raise ValueError("PUBLIC_BASE_URL not configured")


def invite_path(kind: InviteKind, token: str) -> str:
    """Relative path for the SPA router (dedicated route per invitation type)."""
    safe = quote(token.strip(), safe="")
    if kind == "admin":
        return f"/invite/admin/{safe}"
    if kind == "member":
        return f"/invite/member/{safe}"
    return f"/join/{safe}"


def build_invite_url(kind: InviteKind, token: str, *, request: Request | None = None) -> str:
    base = resolve_public_base_url(request=request)
    return f"{base}{invite_path(kind, token)}"


def try_build_invite_url(kind: InviteKind, token: str, *, request: Request | None = None) -> str | None:
    try:
        return build_invite_url(kind, token, request=request)
    except ValueError:
        return None


def absolute_from_invite_path(path: str, *, request: Request | None = None) -> str:
    """Return a full URL for a relative invite path (never a bare path)."""
    if not path:
        raise ValueError("empty invite path")
    trimmed = path.strip()
    if trimmed.startswith("http://") or trimmed.startswith("https://"):
        return trimmed
    rel = trimmed if trimmed.startswith("/") else f"/{trimmed}"
    base = resolve_public_base_url(request=request)
    return f"{base}{rel}"


def try_absolute_from_invite_path(path: str, *, request: Request | None = None) -> str | None:
    try:
        return absolute_from_invite_path(path, request=request)
    except ValueError:
        return None

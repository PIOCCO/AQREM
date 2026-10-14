from __future__ import annotations

import ipaddress

from fastapi import HTTPException, Request

from app.config import Settings


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return ""


def _ip_allowed(ip: str, cidrs: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for part in cidrs.split(","):
        part = part.strip()
        if not part:
            continue
        if addr in ipaddress.ip_network(part, strict=False):
            return True
    return False


def require_internal_caller(request: Request, settings: Settings, x_platform_token: str | None) -> None:
    """Restrict /internal/* to private network CIDRs (not reachable via Front Door)."""
    ip = _client_ip(request)
    if not _ip_allowed(ip, settings.internal_allowed_cidrs):
        raise HTTPException(status_code=403, detail="Internal API not reachable from this network")
    expected = settings.internal_provisioning_token
    if not expected or not x_platform_token or x_platform_token != expected:
        raise HTTPException(status_code=403, detail="Forbidden")

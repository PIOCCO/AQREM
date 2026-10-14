from __future__ import annotations

import ipaddress

from fastapi import HTTPException, Request

from app.config import Settings
from app.entra_auth import validate_entra_bearer


def _peer_ip(request: Request) -> str:
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


def trusted_client_ip(request: Request, settings: Settings) -> str:
    """Use X-Forwarded-For only when the immediate peer is a trusted platform proxy."""
    peer = _peer_ip(request)
    if peer and _ip_allowed(peer, settings.trusted_proxy_cidrs):
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return peer


def require_internal_caller(request: Request, settings: Settings, authorization: str | None) -> None:
    """Entra bearer token from provisioning identity + private-network IP (XFF not trusted from public)."""
    client_ip = trusted_client_ip(request, settings)
    if not _ip_allowed(client_ip, settings.internal_allowed_cidrs):
        raise HTTPException(status_code=403, detail="Internal API not reachable from this network")

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization[7:].strip()
    validate_entra_bearer(token, settings)

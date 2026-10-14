from __future__ import annotations

import json
import time
import urllib.request
from typing import Any

import jwt
from fastapi import HTTPException

from app.config import Settings

_jwks_cache: dict[str, Any] = {"keys": [], "fetched_at": 0.0}


def _tenant_id(settings: Settings) -> str:
    tid = settings.azure_tenant_id
    if not tid:
        raise HTTPException(status_code=503, detail="Gateway Entra tenant not configured")
    return tid


def _fetch_jwks(tenant_id: str) -> dict[str, Any]:
    global _jwks_cache
    if time.time() - _jwks_cache["fetched_at"] < 3600 and _jwks_cache["keys"]:
        return _jwks_cache
    url = f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
    with urllib.request.urlopen(url, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    _jwks_cache = {"keys": data.get("keys", []), "fetched_at": time.time()}
    return _jwks_cache


def validate_entra_bearer(token: str, settings: Settings) -> dict[str, Any]:
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    tenant_id = _tenant_id(settings)
    audience = settings.internal_provisioning_audience
    if not audience:
        raise HTTPException(status_code=503, detail="Gateway internal audience not configured")
    allowed = {x.strip() for x in (settings.internal_provisioning_allowed_object_ids or "").split(",") if x.strip()}
    if not allowed:
        raise HTTPException(status_code=503, detail="Gateway provisioning object ids not configured")

    jwks = _fetch_jwks(tenant_id)
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid token header") from exc
    key = next((k for k in jwks["keys"] if k.get("kid") == header.get("kid")), None)
    if not key:
        raise HTTPException(status_code=401, detail="Unknown signing key")
    public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key))
    try:
        claims = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=audience,
            options={"verify_iss": False},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    iss = claims.get("iss", "")
    if not iss.startswith(f"https://login.microsoftonline.com/{tenant_id}/"):
        raise HTTPException(status_code=401, detail="Invalid issuer")
    oid = claims.get("oid") or claims.get("sub")
    if str(oid) not in allowed:
        raise HTTPException(status_code=403, detail="Provisioning identity not allowed")
    return claims

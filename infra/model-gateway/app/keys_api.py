"""Internal key provisioning API (called by onboarding worker with platform auth)."""

from __future__ import annotations

import secrets
import uuid

import bcrypt
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.db import connection
from app.internal_auth import require_internal_caller

router = APIRouter(prefix="/internal/v1/keys", tags=["internal-keys"])


class MintKeyRequest(BaseModel):
    client_id: str
    organization_id: uuid.UUID
    label: str = Field(pattern="^(primary|secondary)$")
    rpm_limit: int = 60
    tpm_limit: int = 60000
    monthly_token_budget: int = 5_000_000


class MintKeyResponse(BaseModel):
    api_key_plaintext: str
    key_prefix: str
    label: str


@router.post("/mint", response_model=MintKeyResponse)
def mint_key(
    body: MintKeyRequest,
    request: Request,
    x_platform_token: str | None = Header(default=None),
) -> MintKeyResponse:
    settings = get_settings()
    require_internal_caller(request, settings, x_platform_token)
    raw = f"gw_{secrets.token_urlsafe(32)}"
    prefix = raw[:8]
    hashed = bcrypt.hashpw(raw.encode("utf-8"), bcrypt.gensalt())
    with connection(settings) as conn:
        conn.execute(
            """
            INSERT INTO gateway.client (client_id, organization_id, rpm_limit, tpm_limit, monthly_token_budget)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (client_id) DO UPDATE SET
              organization_id = EXCLUDED.organization_id,
              rpm_limit = EXCLUDED.rpm_limit,
              tpm_limit = EXCLUDED.tpm_limit,
              monthly_token_budget = EXCLUDED.monthly_token_budget,
              active = TRUE
            """,
            (
                body.client_id,
                str(body.organization_id),
                body.rpm_limit,
                body.tpm_limit,
                body.monthly_token_budget,
            ),
        )
        conn.execute(
            """
            INSERT INTO gateway.api_key (client_id, key_prefix, key_hash, label, active)
            VALUES (%s, %s, %s, %s, TRUE)
            ON CONFLICT (client_id, label) DO UPDATE SET
              key_prefix = EXCLUDED.key_prefix,
              key_hash = EXCLUDED.key_hash,
              active = TRUE
            """,
            (body.client_id, prefix, hashed, body.label),
        )
    return MintKeyResponse(api_key_plaintext=raw, key_prefix=prefix, label=body.label)


@router.post("/rotate", response_model=MintKeyResponse)
def rotate_key(
    body: MintKeyRequest,
    request: Request,
    x_platform_token: str | None = Header(default=None),
) -> MintKeyResponse:
    """Mint into primary or secondary; at most two active labels per client."""
    settings = get_settings()
    require_internal_caller(request, settings, x_platform_token)
    with connection(settings) as conn:
        count = conn.execute(
            "SELECT count(*) AS c FROM gateway.api_key WHERE client_id = %s AND active",
            (body.client_id,),
        ).fetchone()
        if count and int(count["c"]) >= 2 and body.label not in ("primary", "secondary"):
            raise HTTPException(status_code=400, detail="Invalid label")
    return mint_key(body, request, x_platform_token)


@router.post("/revoke/{client_id}")
def revoke_client(
    client_id: str,
    request: Request,
    x_platform_token: str | None = Header(default=None),
) -> dict[str, str]:
    settings = get_settings()
    require_internal_caller(request, settings, x_platform_token)
    with connection(settings) as conn:
        conn.execute("UPDATE gateway.client SET active = FALSE WHERE client_id = %s", (client_id,))
        conn.execute("UPDATE gateway.api_key SET active = FALSE WHERE client_id = %s", (client_id,))
    return {"status": "revoked"}

"""Platform-managed OpenAI / model token metadata (secrets in Key Vault only)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.audit.service import record_audit
from app.models.client_admin import ClientCredentialMetadata
from app.schemas.org_admin import ModelTokenResponse
from app.services.client_secrets.vault_store import get_client_secret_store
from app.services.telemetry_ingest import ingest_org_telemetry


def get_model_token_response(db: Session, *, organization_id: UUID) -> ModelTokenResponse:
    cred = db.query(ClientCredentialMetadata).filter(ClientCredentialMetadata.organization_id == organization_id).first()
    if cred is None:
        return ModelTokenResponse(
            masked_value="Not configured",
            status="not_configured",
            expires_at=None,
            last_rotated_at=None,
            last_test_at=None,
            last_test_status=None,
        )
    warning = None
    if cred.expires_at:
        days = (cred.expires_at - datetime.now(UTC)).days
        if days <= 30:
            warning = days
    return ModelTokenResponse(
        masked_value=cred.masked_hint,
        status=cred.status,
        expires_at=cred.expires_at,
        last_rotated_at=cred.last_rotated_at,
        last_test_at=cred.last_test_at,
        last_test_status=cred.last_test_status,
        expiry_warning_days=warning,
    )


def save_model_token_for_org(
    db: Session,
    *,
    organization_id: UUID,
    actor_user_id: UUID,
    token: str,
) -> ModelTokenResponse:
    store = get_client_secret_store()
    vault_ref = store.write_model_token(organization_id, token.strip())
    hint = f"****{token.strip()[-4:]}" if len(token.strip()) >= 4 else "****"
    cred = db.query(ClientCredentialMetadata).filter(ClientCredentialMetadata.organization_id == organization_id).first()
    now = datetime.now(UTC)
    expires = now + timedelta(days=365)
    if cred is None:
        cred = ClientCredentialMetadata(
            organization_id=organization_id,
            vault_secret_name=vault_ref,
            masked_hint=hint,
            status="connected",
            expires_at=expires,
            last_rotated_at=now,
        )
        db.add(cred)
    else:
        cred.vault_secret_name = vault_ref
        cred.masked_hint = hint
        cred.status = "connected"
        cred.last_rotated_at = now
        cred.expires_at = expires
    db.flush()
    record_audit(
        db,
        organization_id=organization_id,
        user_id=actor_user_id,
        action="model_token_configured",
        resource_type="credential",
        resource_id=str(cred.id),
        metadata={"status": cred.status, "source": "platform_control_plane"},
    )
    ingest_org_telemetry(
        db,
        organization_id=organization_id,
        event_type="credential.expiry_metadata_updated",
        payload={"expires_at_iso": expires.date().isoformat(), "status": cred.status},
    )
    ok, test_message = store.test_model_token(organization_id)
    cred.last_test_at = datetime.now(UTC)
    cred.last_test_status = "success" if ok else "failed"
    record_audit(
        db,
        organization_id=organization_id,
        user_id=actor_user_id,
        action="model_token_tested",
        resource_type="credential",
        resource_id=str(cred.id),
        metadata={"result": cred.last_test_status, "trigger": "save", "source": "platform_control_plane"},
    )
    db.commit()
    if not ok:
        raise ValueError(test_message or "Token was saved but the connection test failed.")
    return get_model_token_response(db, organization_id=organization_id)


def test_model_token_for_org(db: Session, *, organization_id: UUID, actor_user_id: UUID) -> tuple[bool, str]:
    cred = db.query(ClientCredentialMetadata).filter(ClientCredentialMetadata.organization_id == organization_id).first()
    if cred is None:
        raise LookupError("NOT_CONFIGURED")
    ok, message = get_client_secret_store().test_model_token(organization_id)
    cred.last_test_at = datetime.now(UTC)
    cred.last_test_status = "success" if ok else "failed"
    record_audit(
        db,
        organization_id=organization_id,
        user_id=actor_user_id,
        action="model_token_tested",
        resource_type="credential",
        resource_id=str(cred.id),
        metadata={"result": cred.last_test_status, "source": "platform_control_plane"},
    )
    db.commit()
    return ok, message

"""Client-admin setup checklist from verified backend state."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.client_admin import ClientCredentialMetadata, ClientDocument
from app.models.enums import SourceStatus, SyncJobStatus
from app.models.evidence import EvidenceItem
from app.models.invitation import UserInvitation
from app.models.organization import Organization
from app.models.source import Source, SourceSyncJob
from app.models.tenant_data_store import TenantDataStoreConfig
from app.services.seat_usage import get_seat_usage
from app.tenant_store.resolver import CUSTOMER_POSTGRES, MANAGED_COLOCATED, ensure_managed_config


def _step(status: str, *, title: str, detail: str, step_id: str) -> dict:
    return {"id": step_id, "title": title, "status": status, "detail": detail}


def build_setup_checklist(
    db: Session,
    *,
    organization_id: UUID,
    control_db: Session | None = None,
) -> dict:
    settings = get_settings()
    ctrl = control_db or db
    org = ctrl.get(Organization, organization_id)
    storage_ok = bool(settings.azure_storage_connection_string or settings.local_upload_dir)
    env_ready = bool(org and org.is_active and storage_ok)

    cred = ctrl.query(ClientCredentialMetadata).filter(ClientCredentialMetadata.organization_id == organization_id).first()
    token_connected = (
        cred is not None
        and cred.status in {"connected", "expiring_soon"}
        and cred.last_test_status == "success"
    )

    store_cfg = ensure_managed_config(ctrl, organization_id)
    postgres_ok = _postgres_storage_ready(store_cfg)

    doc_total = db.query(ClientDocument).filter(ClientDocument.organization_id == organization_id).count()
    indexed_docs = (
        db.query(ClientDocument)
        .filter(ClientDocument.organization_id == organization_id, ClientDocument.status == "indexed")
        .count()
    )
    indexing_docs = (
        db.query(ClientDocument)
        .filter(ClientDocument.organization_id == organization_id, ClientDocument.status.in_(("uploading", "indexing")))
        .count()
    )
    evidence_count = db.query(EvidenceItem).filter(EvidenceItem.organization_id == organization_id).count()
    ready_sources = (
        db.query(Source)
        .filter(Source.organization_id == organization_id, Source.status == SourceStatus.READY.value)
        .count()
    )
    failed_jobs = (
        db.query(SourceSyncJob)
        .filter(SourceSyncJob.organization_id == organization_id, SourceSyncJob.status == SyncJobStatus.FAILED.value)
        .count()
    )

    documents_ok = indexed_docs > 0 or (evidence_count > 0 and failed_jobs == 0)
    documents_status = "complete" if documents_ok else ("in_progress" if doc_total or indexing_docs else "pending")

    usage = get_seat_usage(db, org) if org else None
    pending_invites = (
        ctrl.query(UserInvitation)
        .filter(UserInvitation.organization_id == organization_id, UserInvitation.used_at.is_(None))
        .count()
        if org
        else 0
    )
    access_ok = usage is not None and (usage.active_members > 1 or pending_invites > 0)
    access_status = "complete" if access_ok else "pending"

    link_status = "locked" if not access_ok else "complete"

    steps = [
        _step(
            "complete" if env_ready else "pending",
            step_id="environment",
            title="Environment ready",
            detail="Organization and private storage are configured."
            if env_ready
            else "Waiting for organization activation and storage.",
        ),
        _step(
            "complete" if token_connected else "pending",
            step_id="model_token",
            title="OpenAI API token connected",
            detail="OpenAI API token saved and connection test succeeded."
            if token_connected
            else _model_token_detail(cred),
        ),
        _step(
            "complete" if postgres_ok else "pending",
            step_id="postgres_database",
            title="PostgreSQL database configured",
            detail=_postgres_detail(store_cfg, postgres_ok),
        ),
        _step(
            documents_status,
            step_id="documents",
            title="Documents uploaded and indexed",
            detail=f"{indexed_docs} indexed · {indexing_docs} in progress · {ready_sources} sources ready",
        ),
        _step(
            access_status,
            step_id="access",
            title="Employee access configured",
            detail=f"{usage.active_members if usage else 0} active members · {pending_invites} pending invites"
            if usage
            else "Invite at least one employee.",
        ),
        _step(
            link_status,
            step_id="employee_link",
            title="Employee link ready to share",
            detail="Copy the assistant link for your team."
            if access_ok
            else "Complete access setup to enable sharing.",
        ),
    ]

    incomplete = sum(1 for s in steps if s["status"] not in {"complete"})
    completed = sum(1 for s in steps if s["status"] == "complete")
    return {
        "steps": steps,
        "completed_count": completed,
        "total_count": len(steps),
        "incomplete_count": incomplete,
        "percent": int((completed / len(steps)) * 100) if steps else 0,
        "employee_link_enabled": access_ok,
        "storage_configured": storage_ok,
        "model_token_status": cred.status if cred else "not_configured",
        "postgres_database_status": _postgres_status_label(store_cfg, postgres_ok),
    }


def _model_token_detail(cred: ClientCredentialMetadata | None) -> str:
    if cred is None or cred.status == "not_configured":
        return "Add your OpenAI API key, save it to Key Vault, then run Test connection."
    if cred.last_test_status == "failed":
        return "Token is saved but the last connection test failed. Fix the key and test again."
    if cred.last_test_status != "success":
        return "Token is saved. Run Test connection to verify before continuing setup."
    return "Add your OpenAI API key — it is never stored in the platform database."


def _postgres_storage_ready(cfg: TenantDataStoreConfig) -> bool:
    if cfg.paused or cfg.status != "active":
        return False
    if cfg.storage_mode == MANAGED_COLOCATED:
        return True
    if cfg.storage_mode == CUSTOMER_POSTGRES:
        return cfg.last_health_status == "healthy" and bool(cfg.secret_reference and cfg.host and cfg.database_name)
    return False


def _postgres_detail(cfg: TenantDataStoreConfig, ok: bool) -> str:
    if ok and cfg.storage_mode == MANAGED_COLOCATED:
        return "Using AQREM-managed PostgreSQL for your tenant data."
    if ok and cfg.storage_mode == CUSTOMER_POSTGRES:
        host = cfg.host or "your database"
        return f"Connected to {host} (validated)."
    if cfg.storage_mode == CUSTOMER_POSTGRES and cfg.last_health_status == "failed":
        return "Your PostgreSQL connection failed validation. Review Settings and run preflight again."
    return "Choose AQREM-managed PostgreSQL or connect your own database in Settings."


def _postgres_status_label(cfg: TenantDataStoreConfig, ok: bool) -> str:
    if not ok:
        return "not_configured"
    if cfg.storage_mode == MANAGED_COLOCATED:
        return "managed"
    return "customer_connected"

"""Client-admin setup checklist from verified backend state."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.llm_config import inspect_azure_openai
from app.models.enums import SourceStatus, SyncJobStatus
from app.models.evidence import EvidenceItem
from app.models.organization import Organization
from app.models.source import Source, SourceSyncJob
from app.services.seat_usage import get_seat_usage


def build_setup_checklist(db: Session, *, organization_id: UUID) -> dict:
    settings = get_settings()
    org = db.get(Organization, organization_id)
    sources = db.query(Source).filter(Source.organization_id == organization_id).count()
    ready_sources = (
        db.query(Source)
        .filter(Source.organization_id == organization_id, Source.status == SourceStatus.READY.value)
        .count()
    )
    evidence_count = db.query(EvidenceItem).filter(EvidenceItem.organization_id == organization_id).count()
    failed_jobs = (
        db.query(SourceSyncJob)
        .filter(SourceSyncJob.organization_id == organization_id, SourceSyncJob.status == SyncJobStatus.FAILED.value)
        .count()
    )
    running_jobs = (
        db.query(SourceSyncJob)
        .filter(SourceSyncJob.organization_id == organization_id, SourceSyncJob.status == SyncJobStatus.RUNNING.value)
        .count()
    )
    usage = get_seat_usage(db, org) if org else None

    storage_ok = bool(settings.azure_storage_connection_string or settings.local_upload_dir)
    az = inspect_azure_openai(settings)
    ai_status = "configured" if az.configured else "not_configured"

    steps = [
        {
            "id": "organization",
            "title": "Organization identity",
            "status": "complete" if org else "pending",
            "detail": org.name if org else "Organization not found",
        },
        {
            "id": "storage",
            "title": "Private storage",
            "status": "complete" if storage_ok else "pending",
            "detail": "Blob or local upload path configured" if storage_ok else "Storage not configured",
        },
        {
            "id": "ai",
            "title": "Model token / AI provider",
            "status": "complete" if az.configured else "pending",
            "detail": "Azure OpenAI configured" if az.configured else "Configure LLM_PROVIDER=azure with deployment settings",
        },
        {
            "id": "sources",
            "title": "Source connections",
            "status": "complete" if ready_sources > 0 else ("in_progress" if sources > 0 else "pending"),
            "detail": f"{ready_sources} ready of {sources} sources",
        },
        {
            "id": "indexing",
            "title": "Document ingestion",
            "status": "complete"
            if evidence_count > 0 and failed_jobs == 0
            else ("attention" if failed_jobs else ("in_progress" if running_jobs else "pending")),
            "detail": f"{evidence_count} indexed chunks; {failed_jobs} failed jobs; {running_jobs} running",
        },
        {
            "id": "employees",
            "title": "Employee accounts",
            "status": "complete"
            if usage and usage.active_members > 0
            else "pending",
            "detail": f"{usage.active_members if usage else 0} active members"
            + (f" ({usage.seats_used}/{usage.seats_limit} seats)" if usage else ""),
        },
    ]
    completed = sum(1 for s in steps if s["status"] == "complete")
    return {
        "steps": steps,
        "completed_count": completed,
        "total_count": len(steps),
        "percent": int((completed / len(steps)) * 100) if steps else 0,
        "ai_provider_status": ai_status,
        "storage_configured": storage_ok,
    }

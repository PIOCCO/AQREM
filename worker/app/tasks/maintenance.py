"""Background maintenance (stuck documents, audit retention)."""

from __future__ import annotations

from app.services.ingestion.stale_sweep import sweep_all_tenant_documents
from worker.app.celery_app import celery_app


@celery_app.task(name="worker.app.tasks.maintenance.sweep_stuck_documents")
def sweep_stuck_documents() -> dict:
    return sweep_all_tenant_documents()

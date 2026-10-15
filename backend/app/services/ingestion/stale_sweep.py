"""Mark stalled document indexing jobs and optionally re-queue once."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.client_admin import ClientDocument
from app.models.enums import SyncJobStatus
from app.models.organization import Organization
from app.models.source import SourceSyncJob
from app.services.ingestion.document_progress import mark_document_failed
from app.services.ingestion.enqueue import enqueue_source_sync_for_job
from app.tenant_store.resolver import open_tenant_session


def sweep_stalled_documents_for_org(control_db: Session, organization_id: UUID) -> dict:
    settings = get_settings()
    stale_cutoff = datetime.now(UTC) - timedelta(seconds=settings.indexing_stale_seconds)
    max_cutoff = datetime.now(UTC) - timedelta(seconds=settings.indexing_max_seconds)
    tenant_db = open_tenant_session(control_db, organization_id)
    requeued = 0
    failed = 0
    try:
        active = (
            tenant_db.query(ClientDocument)
            .filter(ClientDocument.organization_id == organization_id)
            .filter(ClientDocument.status.in_(("queued", "indexing", "uploading")))
            .all()
        )
        for doc in active:
            job = tenant_db.get(SourceSyncJob, doc.sync_job_id) if doc.sync_job_id else None
            progress_at = doc.index_progress_updated_at or (job.started_at if job else None) or doc.created_at
            if progress_at and progress_at.tzinfo is None:
                progress_at = progress_at.replace(tzinfo=UTC)
            too_old = progress_at is not None and progress_at < max_cutoff
            stale = progress_at is not None and progress_at < stale_cutoff
            if not stale and not too_old:
                continue
            if doc.stall_retry_count < 1 and job and doc.blob_path:
                doc.stall_retry_count += 1
                new_job = SourceSyncJob(
                    organization_id=organization_id,
                    source_id=doc.source_id,
                    status=SyncJobStatus.QUEUED.value,
                    stats={"uploaded_blobs": [doc.blob_path], "client_document_id": str(doc.id)},
                )
                tenant_db.add(new_job)
                tenant_db.flush()
                doc.sync_job_id = new_job.id
                doc.status = "indexing"
                doc.index_stage = "queued"
                doc.failure_reason = None
                tenant_db.commit()
                try:
                    enqueue_source_sync_for_job(
                        tenant_db,
                        job=new_job,
                        organization_id=organization_id,
                        document_ids=[doc.id],
                    )
                    requeued += 1
                except Exception:
                    tenant_db.rollback()
                    mark_document_failed(
                        tenant_db,
                        doc,
                        "Indexing stopped responding. Retry or contact your admin.",
                    )
                    failed += 1
                    tenant_db.commit()
                continue
            mark_document_failed(
                tenant_db,
                doc,
                "Indexing stopped responding. Retry or contact your admin.",
            )
            if job:
                job.status = SyncJobStatus.FAILED.value
                job.error_message = doc.failure_reason
                job.completed_at = datetime.now(UTC)
            failed += 1
        tenant_db.commit()
    finally:
        tenant_db.close()
    return {"requeued": requeued, "failed": failed}


def sweep_all_tenant_documents() -> dict:
    control = SessionLocal()
    totals = {"requeued": 0, "failed": 0, "orgs": 0}
    try:
        org_ids = [row[0] for row in control.query(Organization.id).filter(Organization.deleted_at.is_(None)).all()]
        for org_id in org_ids:
            try:
                result = sweep_stalled_documents_for_org(control, org_id)
                totals["requeued"] += result["requeued"]
                totals["failed"] += result["failed"]
                totals["orgs"] += 1
            except Exception:
                continue
    finally:
        control.close()
    return totals

"""Background maintenance (stuck documents, audit retention)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.client_admin import ClientDocument
from app.models.enums import SyncJobStatus
from app.models.source import SourceSyncJob
from worker.app.celery_app import celery_app

_STUCK_MINUTES = 45


@celery_app.task(name="worker.app.tasks.maintenance.sweep_stuck_documents")
def sweep_stuck_documents() -> dict:
    db: Session = SessionLocal()
    try:
        cutoff = datetime.now(UTC) - timedelta(minutes=_STUCK_MINUTES)
        stuck_docs = (
            db.query(ClientDocument)
            .filter(ClientDocument.status.in_(["uploading", "indexing", "queued"]))
            .all()
        )
        updated = 0
        for doc in stuck_docs:
            job = db.get(SourceSyncJob, doc.sync_job_id) if doc.sync_job_id else None
            stale = job is None or (
                job.status in {SyncJobStatus.QUEUED.value, SyncJobStatus.RUNNING.value}
                and job.started_at is not None
                and job.started_at < cutoff
            )
            if not stale and doc.status == "uploading":
                continue
            if stale or doc.status in {"uploading", "queued"}:
                doc.status = "failed"
                doc.failure_reason = doc.failure_reason or (
                    "Indexing did not complete in time. Retry from the documents page or contact support."
                )
                if job and job.status != SyncJobStatus.FAILED.value:
                    job.status = SyncJobStatus.FAILED.value
                    job.error_message = (job.error_message or "")[:500] or doc.failure_reason
                updated += 1
        db.commit()
        return {"stuck_marked_failed": updated}
    finally:
        db.close()

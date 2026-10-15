"""Enqueue ingestion jobs with explicit errors (no silent failures)."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.broker_health import assert_broker_available
from app.models.client_admin import ClientDocument
from app.models.source import SourceSyncJob

logger = logging.getLogger(__name__)


class IngestionEnqueueError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def enqueue_source_sync_for_job(
    db: Session,
    *,
    job: SourceSyncJob,
    organization_id: UUID,
    document_ids: list[UUID] | None = None,
) -> None:
    assert_broker_available()
    try:
        from worker.app.tasks.ingestion import enqueue_source_sync

        enqueue_source_sync(str(job.id), str(organization_id))
    except Exception as exc:
        logger.warning(
            "ingestion enqueue failed org=%s job=%s type=%s",
            organization_id,
            job.id,
            type(exc).__name__,
        )
        job.status = "failed"
        job.error_message = "Could not queue indexing job (worker or broker unavailable)."
        if document_ids:
            for doc_id in document_ids:
                doc = db.get(ClientDocument, doc_id)
                if doc is None:
                    continue
                doc.status = "queue_failed"
                doc.failure_reason = job.error_message
        raise IngestionEnqueueError("BROKER_UNAVAILABLE", job.error_message) from exc

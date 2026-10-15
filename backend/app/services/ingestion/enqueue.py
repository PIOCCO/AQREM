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
    except ModuleNotFoundError as exc:
        logger.exception(
            "ingestion enqueue import failed org=%s job=%s",
            organization_id,
            job.id,
        )
        job.status = "failed"
        job.error_message = (
            "Could not load the indexing worker module. Rebuild api and worker images "
            "(docker compose … up -d --build api worker)."
        )
        raise IngestionEnqueueError("WORKER_MODULE_UNAVAILABLE", job.error_message) from exc
    except Exception as exc:
        logger.warning(
            "ingestion enqueue failed org=%s job=%s type=%s detail=%s",
            organization_id,
            job.id,
            type(exc).__name__,
            str(exc)[:500],
            exc_info=logger.isEnabledFor(logging.DEBUG),
        )
        job.status = "failed"
        job.error_message = "Could not queue indexing job (worker or broker unavailable)."
        raise IngestionEnqueueError("BROKER_UNAVAILABLE", job.error_message) from exc

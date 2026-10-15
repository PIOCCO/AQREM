"""Persist indexing progress on client_documents for API/UI."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.client_admin import ClientDocument

STAGE_QUEUED = "queued"
STAGE_READING = "reading"
STAGE_PARSING = "parsing"
STAGE_CHUNKING = "chunking"
STAGE_EMBEDDING = "embedding"
STAGE_WRITING = "writing"
STAGE_INDEXED = "indexed"
STAGE_FAILED = "failed"
STAGE_EMPTY = "empty"


def _now() -> datetime:
    return datetime.now(UTC)


def _percent(processed: int, total: int | None) -> int:
    if total is None or total <= 0:
        return 0
    return min(100, int(round(100 * processed / total)))


def load_document_for_job(db: Session, job_stats: dict | None) -> ClientDocument | None:
    if not job_stats:
        return None
    raw = job_stats.get("client_document_id")
    if not raw:
        return None
    try:
        return db.get(ClientDocument, UUID(str(raw)))
    except (ValueError, TypeError):
        return None


def mark_document_progress(
    db: Session,
    doc: ClientDocument,
    *,
    stage: str,
    processed_units: int = 0,
    total_units: int | None = None,
    status: str | None = None,
    failure_reason: str | None = None,
    indexed_chunk_count: int | None = None,
) -> None:
    now = _now()
    if doc.index_started_at is None and stage not in {STAGE_QUEUED, STAGE_FAILED, STAGE_EMPTY}:
        doc.index_started_at = now
    doc.index_stage = stage
    doc.processed_units = processed_units
    doc.total_units = total_units
    doc.index_progress = _percent(processed_units, total_units)
    doc.index_progress_updated_at = now
    if status:
        doc.status = status
    if failure_reason is not None:
        doc.failure_reason = failure_reason
    if indexed_chunk_count is not None:
        doc.indexed_chunk_count = indexed_chunk_count
    if stage in {STAGE_INDEXED, STAGE_FAILED, STAGE_EMPTY}:
        doc.index_finished_at = now
        if stage == STAGE_INDEXED:
            doc.index_progress = 100
    db.flush()


def mark_document_failed(db: Session, doc: ClientDocument, message: str) -> None:
    mark_document_progress(
        db,
        doc,
        stage=STAGE_FAILED,
        status="failed",
        failure_reason=message[:2000],
    )


def mark_document_empty(db: Session, doc: ClientDocument) -> None:
    mark_document_progress(
        db,
        doc,
        stage=STAGE_EMPTY,
        status="failed",
        failure_reason="File is empty, nothing to index.",
        processed_units=0,
        total_units=0,
    )

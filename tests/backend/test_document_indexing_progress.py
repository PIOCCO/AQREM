"""Document indexing progress helpers."""

from __future__ import annotations

from uuid import uuid4

from app.models.client_admin import ClientDocument
from app.services.ingestion.document_progress import mark_document_empty, mark_document_progress, STAGE_EMBEDDING


def test_empty_file_marks_failed_with_message(db_session):
    doc = ClientDocument(
        organization_id=uuid4(),
        file_name="empty.txt",
        content_type="text/plain",
        size_bytes=0,
        blob_path="x/y/empty.txt",
        status="indexing",
    )
    db_session.add(doc)
    db_session.flush()
    mark_document_empty(db_session, doc)
    assert doc.status == "failed"
    assert "empty" in (doc.failure_reason or "").lower()
    assert doc.index_stage == "empty"


def test_progress_percent_from_units(db_session):
    doc = ClientDocument(
        organization_id=uuid4(),
        file_name="a.txt",
        content_type="text/plain",
        size_bytes=10,
        blob_path="x/a.txt",
        status="indexing",
    )
    db_session.add(doc)
    db_session.flush()
    mark_document_progress(db_session, doc, stage=STAGE_EMBEDDING, processed_units=2, total_units=8, status="indexing")
    assert doc.index_progress == 25
    assert doc.processed_units == 2
    assert doc.total_units == 8

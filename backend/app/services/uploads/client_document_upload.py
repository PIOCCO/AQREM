"""Shared ClientDocument upload + ingestion enqueue (Documents page and chat)."""

from __future__ import annotations

import hashlib
from uuid import UUID

from sqlalchemy.orm import Session

from app.audit.service import record_audit
from app.core.config import Settings, get_settings
from app.models.client_admin import ClientDocument
from app.models.enums import SyncJobStatus
from app.models.organization import Organization
from app.models.project import Project
from app.models.source import Source, SourceSyncJob
from app.services.access_control.constants import VISIBILITY_ADMINS_ONLY, VISIBILITY_USERS
from app.services.org_admin.malware_scan import scan_upload_content
from app.services.storage.path_utils import safe_blob_filename
from app.services.access_control.sensitivity import detect_sensitive


def ensure_private_documents_source(db: Session, organization_id: UUID) -> Source:
    project = (
        db.query(Project).filter(Project.organization_id == organization_id).order_by(Project.created_at.asc()).first()
    )
    if project is None:
        project = Project(organization_id=organization_id, name="Private assistant", description="Default project")
        db.add(project)
        db.flush()
    source = (
        db.query(Source)
        .filter(Source.organization_id == organization_id, Source.name == "Private documents")
        .first()
    )
    if source is None:
        from app.models.enums import SourceType

        source = Source(
            organization_id=organization_id,
            project_id=project.id,
            name="Private documents",
            source_type=SourceType.FILE_UPLOAD.value,
            config={},
        )
        db.add(source)
        db.flush()
    return source


def _count_running_ingestion_jobs(db: Session, organization_id: UUID) -> int:
    return (
        db.query(SourceSyncJob)
        .filter(
            SourceSyncJob.organization_id == organization_id,
            SourceSyncJob.status == SyncJobStatus.RUNNING.value,
        )
        .count()
    )


def ingest_client_document_bytes(
    db: Session,
    *,
    organization_id: UUID,
    uploader_user_id: UUID,
    raw_name: str,
    data: bytes,
    content_type: str,
    visibility_mode: str,
    visibility_group_ids: list[UUID] | None = None,
    visibility_user_ids: list[UUID] | None = None,
    audit_action: str = "client_document_uploaded",
    skip_duplicate_hash: bool = True,
) -> ClientDocument:
    settings = get_settings()
    safe_name = safe_blob_filename(raw_name)
    scan_status, scan_reason = scan_upload_content(data)
    if scan_status == "infected":
        raise ValueError(scan_reason or "MALWARE_DETECTED")
    content_hash = hashlib.sha256(data).hexdigest()
    if skip_duplicate_hash:
        duplicate = (
            db.query(ClientDocument)
            .filter(
                ClientDocument.organization_id == organization_id,
                ClientDocument.content_hash == content_hash,
                ClientDocument.status != "failed",
            )
            .first()
        )
        if duplicate:
            raise ValueError("DUPLICATE_FILE")
    source = ensure_private_documents_source(db, organization_id)
    from app.services.storage.factory import get_blob_storage

    storage = get_blob_storage()
    blob_path = f"{organization_id}/{source.id}/{safe_name}"
    storage.upload_bytes(blob_path, data, content_type or "application/octet-stream")
    sensitive, _reason = detect_sensitive(file_name=safe_name, content_sample=data)
    effective_mode = visibility_mode
    if sensitive and visibility_mode == "all_staff":
        effective_mode = VISIBILITY_ADMINS_ONLY
    doc = ClientDocument(
        organization_id=organization_id,
        source_id=source.id,
        file_name=safe_name,
        content_type=content_type or "application/octet-stream",
        size_bytes=len(data),
        blob_path=blob_path,
        status="uploading",
        index_progress=5,
        malware_scan_status=scan_status,
        content_hash=content_hash,
        visibility_mode=effective_mode,
        visibility_group_ids=list(visibility_group_ids or []),
        visibility_user_ids=list(visibility_user_ids or []),
        sensitivity_flag=sensitive,
        acl_reviewed=True,
    )
    db.add(doc)
    db.flush()
    job = SourceSyncJob(
        organization_id=organization_id,
        source_id=source.id,
        status=SyncJobStatus.QUEUED.value,
        stats={"uploaded_blobs": [blob_path], "client_document_id": str(doc.id)},
    )
    db.add(job)
    db.flush()
    doc.sync_job_id = job.id
    doc.status = "indexing"
    record_audit(
        db,
        organization_id=organization_id,
        user_id=uploader_user_id,
        action=audit_action,
        resource_type="client_document",
        resource_id=str(doc.id),
        metadata={"size_bytes": len(data), "file_name": safe_name},
    )
    running = _count_running_ingestion_jobs(db, organization_id)
    if running < settings.chat_attachment_max_concurrent_ingestion:
        try:
            from worker.app.tasks.ingestion import enqueue_source_sync

            enqueue_source_sync(str(job.id), str(organization_id))
        except Exception:
            pass
    db.flush()
    return doc


def chat_attachment_visibility(uploader_user_id: UUID) -> tuple[str, list[UUID]]:
    """Safest default: visible to the uploader (and org admins via ACL rules)."""
    return VISIBILITY_USERS, [uploader_user_id]

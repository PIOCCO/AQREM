"""Chat composer file attachments (reuse ClientDocument ingestion)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.dependencies import get_tenant_context, require_role
from app.core.roles import Role
from app.core.tenant import TenantContext
from app.models.client_admin import ClientDocument
from app.models.enums import SyncJobStatus
from app.models.source import SourceSyncJob
from app.schemas.chat import ChatAttachmentResponse, ChatAttachmentStatusResponse
from app.services.uploads.chat_rate_limit import assert_chat_upload_rate
from app.services.uploads.chat_validation import ChatValidationError, validate_chat_file_content, validate_chat_filename
from app.services.uploads.client_document_upload import chat_attachment_visibility, ingest_client_document_bytes
from app.services.uploads.limits_public import chat_attachment_limits_payload
from app.tenant_store.deps import get_tenant_db

router = APIRouter()


def _sync_doc_from_job(doc: ClientDocument, job: SourceSyncJob | None) -> None:
    if job is None:
        return
    if job.status == SyncJobStatus.QUEUED.value and doc.status in ("uploading", "queued"):
        return
    if job.status == SyncJobStatus.RUNNING.value:
        doc.status = "indexing"
        doc.index_progress = min(95, doc.index_progress + 10 or 10)
    elif job.status == SyncJobStatus.SUCCEEDED.value:
        doc.status = "indexed"
        doc.index_progress = 100
        doc.failure_reason = None
    elif job.status == SyncJobStatus.FAILED.value:
        doc.status = "failed"
        doc.failure_reason = (job.stats or {}).get("error") or job.error_message or "Indexing failed"


def _doc_to_status(doc: ClientDocument) -> ChatAttachmentStatusResponse:
    return ChatAttachmentStatusResponse(
        id=doc.id,
        file_name=doc.file_name,
        size_bytes=doc.size_bytes,
        status=doc.status,
        index_progress=doc.index_progress,
        failure_reason=doc.failure_reason,
    )


@router.get("/attachment-limits")
def get_chat_attachment_limits() -> dict:
    return chat_attachment_limits_payload()


@router.post("/attachments", response_model=ChatAttachmentResponse, status_code=status.HTTP_201_CREATED)
async def upload_chat_attachment(
    file: UploadFile = File(...),
    tenant: TenantContext = Depends(require_role(Role.EDITOR)),
    db: Session = Depends(get_tenant_db),
) -> ChatAttachmentResponse:
    settings = get_settings()
    assert_chat_upload_rate(db, organization_id=tenant.organization_id, user_id=tenant.user_id)
    raw_name = file.filename or "upload.bin"
    try:
        validate_chat_filename(raw_name, settings)
    except ChatValidationError as exc:
        raise HTTPException(status_code=exc.http_status, detail={"code": exc.code, "message": exc.message}) from exc
    data = await file.read()
    try:
        safe_name = raw_name
        from app.services.storage.path_utils import safe_blob_filename

        safe_name = safe_blob_filename(raw_name)
        validate_chat_file_content(safe_name=safe_name, data=data, settings=settings)
    except ChatValidationError as exc:
        raise HTTPException(status_code=exc.http_status, detail={"code": exc.code, "message": exc.message}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "INVALID_FILENAME", "message": str(exc)}) from exc
    vis_mode, vis_users = chat_attachment_visibility(tenant.user_id)
    try:
        doc = ingest_client_document_bytes(
            db,
            organization_id=tenant.organization_id,
            uploader_user_id=tenant.user_id,
            raw_name=raw_name,
            data=data,
            content_type=file.content_type or "application/octet-stream",
            visibility_mode=vis_mode,
            visibility_user_ids=vis_users,
            audit_action="chat_attachment_uploaded",
        )
    except ValueError as exc:
        code = str(exc)
        if code == "DUPLICATE_FILE":
            raise HTTPException(
                status_code=409,
                detail={"code": code, "message": "This file is already attached or uploaded."},
            ) from exc
        raise HTTPException(status_code=400, detail={"code": "UPLOAD_FAILED", "message": code}) from exc
    db.commit()
    db.refresh(doc)
    return ChatAttachmentResponse(
        id=doc.id,
        file_name=doc.file_name,
        size_bytes=doc.size_bytes,
        status=doc.status,
        index_progress=doc.index_progress,
    )


@router.get("/attachments/{document_id}", response_model=ChatAttachmentStatusResponse)
def get_chat_attachment_status(
    document_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_tenant_db),
) -> ChatAttachmentStatusResponse:
    doc = db.get(ClientDocument, document_id)
    if doc is None or doc.organization_id != tenant.organization_id:
        raise HTTPException(status_code=404, detail="Attachment not found")
    if tenant.user_id not in doc.visibility_user_ids and tenant.role not in (Role.ORG_ADMIN, Role.PLATFORM_ADMIN):
        if doc.visibility_mode != "all_staff":
            raise HTTPException(status_code=403, detail="Not allowed to view this attachment")
    if doc.sync_job_id:
        job = db.get(SourceSyncJob, doc.sync_job_id)
        _sync_doc_from_job(doc, job)
        db.commit()
        db.refresh(doc)
    return _doc_to_status(doc)


@router.delete("/attachments/{document_id}", status_code=204)
def delete_chat_attachment(
    document_id: UUID,
    tenant: TenantContext = Depends(require_role(Role.EDITOR)),
    db: Session = Depends(get_tenant_db),
) -> None:
    doc = db.get(ClientDocument, document_id)
    if doc is None or doc.organization_id != tenant.organization_id:
        raise HTTPException(status_code=404, detail="Attachment not found")
    if tenant.user_id not in doc.visibility_user_ids and tenant.role != Role.ORG_ADMIN:
        raise HTTPException(status_code=403, detail="Not allowed to remove this attachment")
    db.delete(doc)
    db.commit()

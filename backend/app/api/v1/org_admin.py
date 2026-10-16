"""Client organization admin console (private assistant dashboard)."""

import hashlib
import os
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.audit.service import record_audit
from app.core.config import get_settings
from app.core.dependencies import require_org_admin
from app.core.org_admin_errors import org_admin_error
from app.core.rate_limit import limiter
from app.core.roles import Role
from app.core.jwt_audiences import AUD_ORG_ADMIN
from app.core.security import decode_access_token
from app.core.tenant import TenantContext
from app.db.session import get_db
from app.tenant_store.deps import get_tenant_db
from app.models.client_admin import ClientDocument
from app.models.enums import EvidenceScope, SourceType, SyncJobStatus
from app.models.invitation import UserInvitation
from app.models.organization import Organization, OrganizationMembership, User
from app.models.project import Project
from app.models.source import Source, SourceSyncJob
from app.models.audit import AuditEvent
from app.schemas.tenant_storage import (
    PreflightReportResponse,
    TenantStorageConfigureRequest,
    TenantStorageResponse,
)
from app.schemas.org_admin import (
    AuditCleanupResponse,
    AuditListResponse,
    AuditRowResponse,
    DocumentListResponse,
    DocumentRowResponse,
    MemberInviteRequest,
    MemberRow,
    UsageSummaryResponse,
)
from app.services.licensing import LicenseDenied, assert_can_add_seat
from app.services.org_admin.malware_scan import scan_upload_content
from app.services.org_admin.policy import PolicyDenied, assert_org_admin_action
from app.services.org_admin.role_assignment import (
    OrgAdminRoleAssignmentDenied,
    assert_org_admin_may_assign_role,
    assert_org_admin_may_remove_membership,
    parse_org_admin_invite_role,
)
from app.services.platform_provisioning import provision_user_invitation
from app.services.setup_checklist import build_setup_checklist
from app.services.seat_usage import get_seat_usage
from app.services.storage.factory import get_blob_storage
from app.services.storage.path_utils import safe_blob_filename
from app.services.membership_lifecycle import (
    MembershipRemoveError,
    normalize_org_admin_singleton,
    purge_legacy_inactive_memberships,
    remove_organization_membership,
)
from app.services.telemetry_ingest import ingest_org_telemetry
from app.services.telemetry_schema import TELEMETRY_FIELD_CATALOG
from app.services.access_control.constants import VISIBILITY_ADMINS_ONLY, VISIBILITY_ALL_STAFF, VISIBILITY_GROUPS, VISIBILITY_USERS
from app.services.access_control.groups import ensure_default_access_groups
from app.services.access_control.sensitivity import detect_sensitive

router = APIRouter()


def _require_org_admin_surface(request: Request, tenant: TenantContext = Depends(require_org_admin)) -> TenantContext:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise org_admin_error(code="UNAUTHORIZED", message="Not authenticated", status_code=401)
    try:
        decode_access_token(auth[7:], audiences=AUD_ORG_ADMIN)
    except ValueError as exc:
        raise org_admin_error(
            code="WRONG_AUDIENCE",
            message="Organization administrator token required.",
            status_code=403,
        ) from exc
    return tenant


def _sync_document_from_job(doc: ClientDocument, job: SourceSyncJob | None) -> None:
    """Align document row with sync job when worker or UI state diverges.

    A completed job is indexed only when it recorded stored embeddings.
    """
    if job is None:
        return
    if job.status == SyncJobStatus.COMPLETED.value:
        stats = job.stats or {}
        if "embedded_chunks" not in stats:
            return
        embedded = int(stats.get("embedded_chunks") or 0)
        if embedded > 0:
            doc.status = "indexed"
            doc.index_progress = 100
            doc.index_stage = "indexed"
            doc.indexed_chunk_count = embedded
            doc.failure_reason = None
        else:
            doc.status = "failed"
            doc.index_stage = "failed"
            doc.indexed_chunk_count = 0
            doc.failure_reason = "Indexing finished without stored embeddings."
        return
    if job.status == SyncJobStatus.FAILED.value:
        if doc.status != "failed" or doc.index_stage != "failed":
            doc.status = "failed"
            doc.index_stage = "failed"
            doc.failure_reason = job.error_message or "Indexing failed"
        return
    if doc.index_progress_updated_at is not None:
        return


def _ensure_document_source(db: Session, tenant: TenantContext) -> Source:
    project = (
        db.query(Project).filter(Project.organization_id == tenant.organization_id).order_by(Project.created_at.asc()).first()
    )
    if project is None:
        project = Project(organization_id=tenant.organization_id, name="Private assistant", description="Default project")
        db.add(project)
        db.flush()
    source = (
        db.query(Source)
        .filter(Source.organization_id == tenant.organization_id, Source.name == "Private documents")
        .first()
    )
    if source is None:
        source = Source(
            organization_id=tenant.organization_id,
            project_id=project.id,
            name="Private documents",
            source_type=SourceType.FOLDER_ARCHIVE.value,
            scope=EvidenceScope.ORGANIZATION.value,
            config={},
        )
        db.add(source)
        db.flush()
    return source


@router.get("/console-enter")
def admin_console_enter(
    request: Request,
    tenant: TenantContext = Depends(_require_org_admin_surface),
    db: Session = Depends(get_tenant_db),
) -> dict[str, bool]:
    from app.services.audit.console_enter import record_admin_console_entered

    record_admin_console_entered(
        db,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        request_id=request.headers.get("X-Request-Id"),
    )
    db.commit()
    return {"ok": True}


@router.get("/setup")
def get_setup_checklist(
    tenant: TenantContext = Depends(_require_org_admin_surface),
    db: Session = Depends(get_tenant_db),
    control_db: Session = Depends(get_db),
) -> dict:
    assert_org_admin_action(tenant, action="read", resource_type="setup", resource_org_id=tenant.organization_id)
    return build_setup_checklist(db, organization_id=tenant.organization_id, control_db=control_db)


@router.get("/overview")
def org_admin_overview(
    tenant: TenantContext = Depends(_require_org_admin_surface),
    db: Session = Depends(get_tenant_db),
    control_db: Session = Depends(get_db),
) -> dict:
    org = control_db.get(Organization, tenant.organization_id)
    checklist = build_setup_checklist(db, organization_id=tenant.organization_id, control_db=control_db)
    usage = get_seat_usage(control_db, org) if org else None
    return {
        "organization": {
            "id": str(org.id) if org else None,
            "name": org.name if org else "",
            "license_limit": org.license_limit if org else 0,
            "license_status": org.license_status if org else "",
        },
        "setup": checklist,
        "seats": {
            "used": usage.seats_used if usage else 0,
            "limit": usage.seats_limit if usage else 0,
            "available": usage.seats_available if usage else 0,
            "is_full": usage.is_full if usage else False,
        },
        "employee_link": {
            "url_path": "/chat",
            "enabled": checklist.get("employee_link_enabled", False),
        },
        "admin_console_path": "/admin",
    }


@router.get("/documents", response_model=DocumentListResponse)
def list_documents(
    tenant: TenantContext = Depends(_require_org_admin_surface),
    db: Session = Depends(get_tenant_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
) -> DocumentListResponse:
    assert_org_admin_action(tenant, action="read", resource_type="document", resource_org_id=tenant.organization_id)
    base = db.query(ClientDocument).filter(ClientDocument.organization_id == tenant.organization_id)
    total = base.count()
    rows = (
        base.order_by(ClientDocument.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    import asyncio
    import logging

    from app.services.ingestion.embedding_health import apply_index_truth, document_search_health, reembed_stale_chunks

    health_log = logging.getLogger("aqrem.rag")
    asyncio.run(reembed_stale_chunks(db, tenant.organization_id))
    health_by_id: dict = {}
    for doc in rows:
        job = db.get(SourceSyncJob, doc.sync_job_id) if doc.sync_job_id else None
        _sync_document_from_job(doc, job)
        health = document_search_health(db, doc)
        apply_index_truth(doc, health)
        health_by_id[doc.id] = health
        health_log.info(
            "document index health file=%s org=%s chunks_stored=%s chunks_with_embedding=%s "
            "vector_size=%s search_ready=%s leftover_project_ids=%s leftover_visibility=%s",
            doc.file_name,
            doc.organization_id,
            health["chunks_stored"],
            health["chunks_with_embedding"],
            health["embedding_dimensions"],
            health["search_ready"],
            health["leftover_project_ids"],
            health["leftover_visibility_modes"],
        )
    db.commit()
    queued_jobs = (
        db.query(SourceSyncJob)
        .filter(
            SourceSyncJob.organization_id == tenant.organization_id,
            SourceSyncJob.status == SyncJobStatus.QUEUED.value,
        )
        .order_by(SourceSyncJob.created_at.asc())
        .all()
    )
    queue_rank = {str(j.id): idx for idx, j in enumerate(queued_jobs)}
    org_docs = db.query(ClientDocument).filter(ClientDocument.organization_id == tenant.organization_id)
    counts = {
        "total": total,
        "indexed": org_docs.filter(ClientDocument.status == "indexed").count(),
        "indexing": org_docs.filter(ClientDocument.status.in_(("uploading", "indexing", "queued"))).count(),
        "failed": org_docs.filter(ClientDocument.status == "failed").count(),
        "needs_visibility_review": org_docs.filter(ClientDocument.acl_reviewed.is_(False)).count(),
    }
    from app.core.broker_health import broker_is_available
    from app.core.config import get_settings

    settings = get_settings()
    worker_ok = broker_is_available()
    queue_warn = False
    now = datetime.now(UTC)
    items: list[DocumentRowResponse] = []
    for r in rows:
        job = db.get(SourceSyncJob, r.sync_job_id) if r.sync_job_id else None
        queue_ahead: int | None = None
        if r.index_stage == "queued" and job is not None:
            queue_ahead = queue_rank.get(str(job.id))
        if (
            job
            and job.status == SyncJobStatus.QUEUED.value
            and job.created_at
            and (now - job.created_at).total_seconds() > settings.queue_wait_warn_seconds
        ):
            queue_warn = True
        items.append(
            DocumentRowResponse(
                id=r.id,
                file_name=r.file_name,
                size_bytes=r.size_bytes,
                content_type=r.content_type,
                status=r.status,
                index_progress=r.index_progress,
                index_stage=r.index_stage,
                processed_units=r.processed_units,
                total_units=r.total_units,
                indexed_chunk_count=r.indexed_chunk_count,
                index_started_at=r.index_started_at,
                index_finished_at=r.index_finished_at,
                index_progress_updated_at=r.index_progress_updated_at,
                queue_ahead=queue_ahead,
                failure_reason=r.failure_reason,
                visibility_mode=r.visibility_mode,
                sensitivity_flag=r.sensitivity_flag,
                acl_reviewed=r.acl_reviewed,
                created_at=r.created_at,
                chunks_stored=health_by_id.get(r.id, {}).get("chunks_stored", 0),
                chunks_with_embedding=health_by_id.get(r.id, {}).get("chunks_with_embedding", 0),
                embedding_dimensions=health_by_id.get(r.id, {}).get("embedding_dimensions"),
                search_ready=bool(health_by_id.get(r.id, {}).get("search_ready", False)),
                leftover_project_ids=health_by_id.get(r.id, {}).get("leftover_project_ids", []),
                leftover_visibility_modes=health_by_id.get(r.id, {}).get("leftover_visibility_modes", []),
            )
        )
    return DocumentListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        counts=counts,
        worker_reachable=worker_ok,
        queue_wait_warning=queue_warn,
    )


@router.post("/documents/upload")
@limiter.limit("20/minute")
async def upload_documents(
    request: Request,
    files: Annotated[list[UploadFile], File()],
    visibility_mode: Annotated[str, Form()],
    visibility_group_ids: Annotated[str | None, Form()] = None,
    tenant: TenantContext = Depends(_require_org_admin_surface),
    db: Session = Depends(get_tenant_db),
    control_db: Session = Depends(get_db),
) -> dict:
    assert_org_admin_action(tenant, action="write", resource_type="document", resource_org_id=tenant.organization_id)
    from app.services.setup_checklist import tenant_database_setup_complete
    from app.tenant_store.resolver import get_tenant_store_config

    store_cfg = get_tenant_store_config(control_db, tenant.organization_id)
    if not tenant_database_setup_complete(store_cfg):
        raise org_admin_error(
            code="DATABASE_NOT_CONFIGURED",
            message="PostgreSQL is not configured yet. Open Data storage, validate your database, and click Save and activate before uploading documents.",
            status_code=503,
        )
    from app.services.storage.health import StorageUnavailable, assert_upload_storage_ready

    try:
        assert_upload_storage_ready()
    except StorageUnavailable as exc:
        raise org_admin_error(code="STORAGE_UNAVAILABLE", message=exc.message, status_code=503) from exc
    ensure_default_access_groups(db, tenant.organization_id)
    settings = get_settings()
    if settings.product_v1:
        visibility_mode = VISIBILITY_ALL_STAFF
    elif visibility_mode not in {VISIBILITY_ALL_STAFF, VISIBILITY_GROUPS, VISIBILITY_USERS, VISIBILITY_ADMINS_ONLY}:
        raise org_admin_error(code="VISIBILITY_REQUIRED", message="Choose who can see these files.", field="visibility_mode")
    group_ids: list[UUID] = []
    if visibility_group_ids:
        for part in visibility_group_ids.split(","):
            part = part.strip()
            if part:
                group_ids.append(UUID(part))
    if visibility_mode == VISIBILITY_GROUPS and not group_ids:
        raise org_admin_error(code="GROUPS_REQUIRED", message="Pick at least one group.", field="visibility_mode")
    source = _ensure_document_source(db, tenant)
    try:
        storage = get_blob_storage()
    except Exception as exc:
        settings = get_settings()
        if settings.use_azure_blob_storage:
            message = (
                "Blob storage is not reachable. For Docker Compose, ensure the azurite service is running "
                "or set LOCAL_UPLOAD_DIR to a writable path and clear AZURE_STORAGE_CONNECTION_STRING."
            )
        else:
            message = (
                f"File storage is not ready at {settings.local_upload_dir}. "
                "For local-prod Docker, recreate api and worker after compose sets LOCAL_UPLOAD_DIR and a shared volume."
            )
        if os.environ.get("LOCAL_PROD_STACK", "").strip().lower() in {"1", "true", "yes"}:
            hint = str(exc).split("\n")[0][:240]
            if hint:
                message = f"{message} ({hint})"
        raise org_admin_error(
            code="STORAGE_UNAVAILABLE",
            message=message,
            status_code=503,
        ) from exc
    from app.services.ingestion.enqueue import IngestionEnqueueError, enqueue_source_sync_for_job

    try:
        from app.core.broker_health import assert_broker_available

        assert_broker_available()
    except RuntimeError as exc:
        raise org_admin_error(
            code="BROKER_UNAVAILABLE",
            message=str(exc),
            status_code=503,
        ) from exc

    created: list[str] = []
    uploaded_blob_paths: list[str] = []
    pending_jobs: list[tuple[SourceSyncJob, UUID]] = []
    for upload in files:
        raw_name = upload.filename or "upload.bin"
        try:
            safe_name = safe_blob_filename(raw_name)
        except ValueError as exc:
            raise org_admin_error(code="INVALID_FILENAME", message="Invalid file name.", field="file") from exc
        ext = safe_name.lower().split(".")[-1]
        if f".{ext}" not in settings.allowed_extensions_set and not any(
            raw_name.lower().endswith(x) for x in settings.allowed_extensions_set
        ):
            raise org_admin_error(
                code="TYPE_NOT_ALLOWED",
                message=f"File type not allowed. Allowed: {', '.join(sorted(settings.allowed_extensions_set))}",
                field="file",
            )
        data = await upload.read()
        if len(data) > settings.max_upload_bytes:
            raise org_admin_error(
                code="FILE_TOO_LARGE",
                message=f"File exceeds {settings.max_upload_bytes // (1024 * 1024)} MB limit.",
                field="file",
                status_code=413,
            )
        scan_status, scan_reason = scan_upload_content(data)
        if scan_status == "infected":
            raise org_admin_error(code="MALWARE_DETECTED", message=scan_reason or "File rejected.", field="file")
        if scan_status == "failed":
            raise org_admin_error(
                code="EMPTY_FILE",
                message=scan_reason or "File is empty.",
                field="file",
            )
        content_hash = hashlib.sha256(data).hexdigest()
        duplicate = (
            db.query(ClientDocument)
            .filter(
                ClientDocument.organization_id == tenant.organization_id,
                ClientDocument.content_hash == content_hash,
                ClientDocument.status != "failed",
            )
            .first()
        )
        if duplicate:
            raise org_admin_error(
                code="DUPLICATE_FILE",
                message="This file was already uploaded.",
                field="file",
            )
        blob_path = f"{tenant.organization_id}/{source.id}/{safe_name}"
        try:
            storage.upload_bytes(blob_path, data, upload.content_type or "application/octet-stream")
            uploaded_blob_paths.append(blob_path)
        except OSError as exc:
            raise org_admin_error(
                code="STORAGE_UNAVAILABLE",
                message=f"Could not save the file to storage. Check LOCAL_UPLOAD_DIR or blob permissions. ({exc.strerror or exc})",
                status_code=503,
            ) from exc
        sensitive, _reason = detect_sensitive(file_name=safe_name, content_sample=data)
        effective_mode = visibility_mode
        if not settings.product_v1 and sensitive and visibility_mode == VISIBILITY_ALL_STAFF:
            effective_mode = VISIBILITY_ADMINS_ONLY
        doc = ClientDocument(
            organization_id=tenant.organization_id,
            source_id=source.id,
            file_name=safe_name,
            content_type=upload.content_type or "application/octet-stream",
            size_bytes=len(data),
            blob_path=blob_path,
            status="queued",
            index_stage="queued",
            index_progress=0,
            malware_scan_status=scan_status,
            content_hash=content_hash,
            visibility_mode=effective_mode,
            visibility_group_ids=group_ids if effective_mode == VISIBILITY_GROUPS else [],
            visibility_user_ids=[],
            sensitivity_flag=sensitive,
            acl_reviewed=True,
        )
        db.add(doc)
        db.flush()
        job = SourceSyncJob(
            organization_id=tenant.organization_id,
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
            organization_id=tenant.organization_id,
            user_id=tenant.user_id,
            action="client_document_uploaded",
            resource_type="client_document",
            resource_id=str(doc.id),
            metadata={"size_bytes": len(data), "content_type": doc.content_type},
        )
        pending_jobs.append((job, doc.id))

    db.commit()

    try:
        for job, doc_id in pending_jobs:
            enqueue_source_sync_for_job(
                db,
                job=job,
                organization_id=tenant.organization_id,
                document_ids=[doc_id],
            )
            created.append(str(doc_id))
    except IngestionEnqueueError as exc:
        for _job, doc_id in pending_jobs:
            failed_doc = db.get(ClientDocument, doc_id)
            failed_job = db.get(SourceSyncJob, _job.id) if _job.id else None
            if failed_job is not None:
                failed_job.status = SyncJobStatus.FAILED.value
                failed_job.error_message = exc.message
            if failed_doc is not None:
                failed_doc.status = "failed"
                failed_doc.index_stage = "failed"
                failed_doc.failure_reason = exc.message
        db.commit()
        for blob_path in uploaded_blob_paths:
            try:
                storage.delete(blob_path)
            except Exception:
                pass
        for _job, doc_id in pending_jobs:
            failed_doc = db.get(ClientDocument, doc_id)
            if failed_doc is not None:
                db.delete(failed_doc)
            if _job.id:
                failed_job = db.get(SourceSyncJob, _job.id)
                if failed_job is not None:
                    db.delete(failed_job)
        db.commit()
        raise org_admin_error(code=exc.code, message=exc.message, status_code=503) from exc

    ingest_org_telemetry(
        db,
        organization_id=tenant.organization_id,
        event_type="document.indexing_job_completed",
        payload={"indexed_count": len(created), "failed_count": 0, "indexing_count": len(created)},
    )
    db.commit()
    return {"document_ids": created}


@router.delete("/documents/{document_id}")
def remove_document(
    document_id: UUID,
    tenant: TenantContext = Depends(_require_org_admin_surface),
    db: Session = Depends(get_tenant_db),
) -> dict:
    assert_org_admin_action(tenant, action="delete", resource_type="document", resource_org_id=tenant.organization_id)
    doc = db.get(ClientDocument, document_id)
    if doc is None or doc.organization_id != tenant.organization_id:
        raise org_admin_error(code="NOT_FOUND", message="Document not found.", status_code=404)
    if doc.sync_job_id:
        job = db.get(SourceSyncJob, doc.sync_job_id)
        if job is not None:
            db.delete(job)
    if doc.blob_path:
        try:
            get_blob_storage().delete(doc.blob_path)
        except Exception:
            pass
    from app.models.evidence import EvidenceItem

    if doc.source_id:
        db.query(EvidenceItem).filter(
            EvidenceItem.organization_id == tenant.organization_id,
            EvidenceItem.source_id == doc.source_id,
            EvidenceItem.file_name == doc.file_name,
        ).delete(synchronize_session=False)
    record_audit(
        db,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        action="client_document_removed",
        resource_type="client_document",
        resource_id=str(doc.id),
        metadata={"size_bytes": doc.size_bytes},
    )
    doc_id = str(doc.id)
    db.delete(doc)
    db.commit()
    return {"deleted": True, "document_id": doc_id}


@router.post("/documents/{document_id}/retry")
def retry_document(
    document_id: UUID,
    tenant: TenantContext = Depends(_require_org_admin_surface),
    db: Session = Depends(get_tenant_db),
) -> dict:
    doc = db.get(ClientDocument, document_id)
    if doc is None or doc.organization_id != tenant.organization_id:
        raise org_admin_error(code="NOT_FOUND", message="Document not found.", status_code=404)
    if not doc.source_id:
        raise org_admin_error(code="INVALID_STATE", message="Document has no source.")
    job = SourceSyncJob(
        organization_id=tenant.organization_id,
        source_id=doc.source_id,
        status=SyncJobStatus.QUEUED.value,
        stats={"uploaded_blobs": [doc.blob_path], "client_document_id": str(doc.id)},
    )
    db.add(job)
    doc.sync_job_id = job.id
    doc.status = "indexing"
    doc.index_stage = "queued"
    doc.index_progress = 0
    doc.processed_units = 0
    doc.total_units = None
    doc.index_started_at = None
    doc.index_finished_at = None
    doc.index_progress_updated_at = None
    doc.indexed_chunk_count = 0
    doc.failure_reason = None
    db.flush()
    db.commit()
    try:
        from app.services.ingestion.enqueue import IngestionEnqueueError, enqueue_source_sync_for_job

        enqueue_source_sync_for_job(db, job=job, organization_id=tenant.organization_id, document_ids=[doc.id])
    except IngestionEnqueueError as exc:
        raise org_admin_error(code=exc.code, message=exc.message, status_code=503) from exc
    return {"job_id": str(job.id)}


_ORG_ADMIN_MODEL_TOKEN_FORBIDDEN = (
    "OpenAI API credentials are configured by the platform super admin team, not in the organization admin console."
)


@router.get("/model-token")
def org_admin_get_model_token_forbidden(
    tenant: TenantContext = Depends(_require_org_admin_surface),
) -> None:
    assert_org_admin_action(tenant, action="read", resource_type="credential", resource_org_id=tenant.organization_id)
    raise org_admin_error(
        code="CREDENTIAL_PLATFORM_MANAGED",
        message=_ORG_ADMIN_MODEL_TOKEN_FORBIDDEN,
        status_code=403,
    )


@router.put("/model-token")
def org_admin_save_model_token_forbidden(
    tenant: TenantContext = Depends(_require_org_admin_surface),
) -> None:
    assert_org_admin_action(tenant, action="write", resource_type="credential", resource_org_id=tenant.organization_id)
    raise org_admin_error(
        code="CREDENTIAL_PLATFORM_MANAGED",
        message=_ORG_ADMIN_MODEL_TOKEN_FORBIDDEN,
        status_code=403,
    )


@router.post("/model-token/test")
def org_admin_test_model_token_forbidden(
    tenant: TenantContext = Depends(_require_org_admin_surface),
) -> None:
    raise org_admin_error(
        code="CREDENTIAL_PLATFORM_MANAGED",
        message=_ORG_ADMIN_MODEL_TOKEN_FORBIDDEN,
        status_code=403,
    )


@router.post("/model-token/rotate")
def org_admin_rotate_model_token_forbidden(
    tenant: TenantContext = Depends(_require_org_admin_surface),
) -> None:
    raise org_admin_error(
        code="CREDENTIAL_PLATFORM_MANAGED",
        message=_ORG_ADMIN_MODEL_TOKEN_FORBIDDEN,
        status_code=403,
    )


@router.get("/members", response_model=list[MemberRow])
def list_members(
    tenant: TenantContext = Depends(_require_org_admin_surface),
    db: Session = Depends(get_tenant_db),
) -> list[MemberRow]:
    assert_org_admin_action(tenant, action="read", resource_type="member", resource_org_id=tenant.organization_id)
    purge_legacy_inactive_memberships(db, tenant.organization_id)
    normalize_org_admin_singleton(db, tenant.organization_id)
    db.flush()
    db.commit()
    rows = (
        db.query(OrganizationMembership, User)
        .join(User, User.id == OrganizationMembership.user_id)
        .filter(
            OrganizationMembership.organization_id == tenant.organization_id,
            OrganizationMembership.is_active.is_(True),
            User.is_active.is_(True),
        )
        .all()
    )
    now = datetime.now(UTC)
    out: list[MemberRow] = []
    for m, u in rows:
        pending_inv = (
            db.query(UserInvitation)
            .filter(
                UserInvitation.organization_id == tenant.organization_id,
                UserInvitation.email == u.email.strip().lower(),
                UserInvitation.invitation_kind == "member",
                UserInvitation.used_at.is_(None),
                UserInvitation.revoked_at.is_(None),
                UserInvitation.expires_at > now,
            )
            .order_by(UserInvitation.created_at.desc())
            .first()
        )
        invite_pending = pending_inv is not None and u.hashed_password is None
        display_name = (
            (pending_inv.invitee_full_name or u.full_name).strip()
            if invite_pending and pending_inv
            else u.full_name
        )
        out.append(
            MemberRow(
                membership_id=m.id,
                user_id=u.id,
                email=u.email,
                full_name=display_name,
                role=m.role,
                is_active=True,
                membership_status="pending" if invite_pending else "active",
            )
        )
    return out


@router.post("/members/invite", status_code=201)
@limiter.limit("30/minute")
def invite_member(
    request: Request,
    payload: MemberInviteRequest,
    tenant: TenantContext = Depends(_require_org_admin_surface),
    db: Session = Depends(get_tenant_db),
) -> dict:
    assert_org_admin_action(tenant, action="write", resource_type="member", resource_org_id=tenant.organization_id)
    org = db.get(Organization, tenant.organization_id)
    if org is None:
        raise org_admin_error(code="NOT_FOUND", message="Organization not found.", status_code=404)
    try:
        assert_can_add_seat(db, org)
    except LicenseDenied as exc:
        raise org_admin_error(code="SEATS_FULL", message=exc.detail, field="email", status_code=403) from exc
    try:
        role = parse_org_admin_invite_role(payload.role)
    except ValueError as exc:
        code = str(exc)
        if code == "MISSING_ROLE":
            raise org_admin_error(code="INVALID_ROLE", message="Choose Editor or Viewer.", field="role") from exc
        raise org_admin_error(code="INVALID_ROLE", message="Choose Editor or Viewer.", field="role") from exc
    try:
        assert_org_admin_may_assign_role(db, tenant, role, context="members_invite")
    except OrgAdminRoleAssignmentDenied as exc:
        db.commit()
        status = 403 if exc.code == "ORG_ADMIN_ASSIGN_FORBIDDEN" else 400
        raise org_admin_error(code=exc.code, message=exc.message, field="role", status_code=status) from exc
    try:
        _user, _membership, invitation, raw_token, expires_at = provision_user_invitation(
            db,
            admin_user_id=tenant.user_id,
            organization_id=tenant.organization_id,
            email=payload.email.lower(),
            full_name=payload.full_name,
            role=role,
        )
    except LicenseDenied as exc:
        raise org_admin_error(code="SEATS_FULL", message=exc.detail, field="email", status_code=403) from exc
    except ValueError as exc:
        if str(exc) == "DUPLICATE_EMAIL":
            raise org_admin_error(code="DUPLICATE_EMAIL", message="An invitation already exists for this email.", field="email") from exc
        raise org_admin_error(code="VALIDATION_ERROR", message=str(exc)) from exc
    record_audit(
        db,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        action="member_invited",
        resource_type="invitation",
        resource_id=str(invitation.id),
        metadata={"role": role.value},
    )
    from app.services.seat_usage import get_seat_usage

    seats = get_seat_usage(db, org)
    ingest_org_telemetry(
        db,
        organization_id=tenant.organization_id,
        event_type="license.seat_usage_changed",
        payload={"seats_used": seats.seats_used, "seats_limit": seats.seats_limit},
    )
    db.commit()
    from app.services.invitations.invite_urls import build_invite_url, invite_path

    path = invite_path("member", raw_token)
    try:
        setup_url = build_invite_url("member", raw_token, request=request)
    except ValueError as exc:
        raise org_admin_error(
            code="PUBLIC_URL_NOT_CONFIGURED",
            message="Invitation was created but the public base URL is not configured. Set PUBLIC_BASE_URL (PUBLIC_APP_URL) on the server or ensure the reverse proxy forwards Host and X-Forwarded-* headers.",
            status_code=503,
        ) from exc
    return {
        "invitation_setup_path": path,
        "invitation_setup_url": setup_url,
        "invite_url": setup_url,
        "expires_at": expires_at.isoformat(),
    }


@router.post("/members/{membership_id}/deactivate", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def deactivate_org_member(
    membership_id: UUID,
    tenant: TenantContext = Depends(_require_org_admin_surface),
    db: Session = Depends(get_tenant_db),
) -> Response:
    assert_org_admin_action(tenant, action="write", resource_type="member", resource_org_id=tenant.organization_id)
    membership = db.get(OrganizationMembership, membership_id)
    if membership is None or membership.organization_id != tenant.organization_id:
        raise org_admin_error(code="NOT_FOUND", message="Member not found.", status_code=404)
    try:
        assert_org_admin_may_remove_membership(
            db,
            tenant,
            target_membership_id=membership.id,
            target_role=membership.role,
        )
    except OrgAdminRoleAssignmentDenied as exc:
        db.commit()
        raise org_admin_error(code=exc.code, message=exc.message, status_code=403) from exc
    try:
        remove_organization_membership(
            db,
            admin_user_id=tenant.user_id,
            membership=membership,
            reason="org_admin_removed",
            source="organization_admin_console",
            audit_action="organization_member_removed",
        )
    except MembershipRemoveError as exc:
        code = str(exc)
        if code == "SELF_REMOVE_FORBIDDEN":
            raise org_admin_error(
                code="SELF_REMOVE_FORBIDDEN",
                message="You cannot remove your own membership.",
                status_code=400,
            ) from exc
        if code == "LAST_ORG_ADMIN":
            raise org_admin_error(
                code="LAST_ORG_ADMIN",
                message="Replace the organization admin before removing them.",
                status_code=409,
            ) from exc
        raise org_admin_error(code=code, message=code.replace("_", " ").capitalize()) from exc
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT, response_class=Response)


@router.get("/usage", response_model=UsageSummaryResponse)
def usage_summary(
    tenant: TenantContext = Depends(_require_org_admin_surface),
    db: Session = Depends(get_tenant_db),
) -> UsageSummaryResponse:
    assert_org_admin_action(tenant, action="read", resource_type="usage", resource_org_id=tenant.organization_id)
    members = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == tenant.organization_id,
            OrganizationMembership.is_active.is_(True),
        )
        .count()
    )
    docs = db.query(ClientDocument).filter(ClientDocument.organization_id == tenant.organization_id)
    storage_bytes = sum(d.size_bytes for d in docs.all())
    indexed = docs.filter(ClientDocument.status == "indexed").count()
    return UsageSummaryResponse(
        queries_last_30_days=0,
        active_users=members,
        storage_bytes=storage_bytes,
        indexed_documents=indexed,
    )


def _audit_rows(
    db: Session,
    organization_id: UUID,
    *,
    page: int,
    page_size: int,
) -> AuditListResponse:
    base = db.query(AuditEvent).filter(AuditEvent.organization_id == organization_id)
    total = base.count()
    rows = (
        db.query(AuditEvent, User)
        .outerjoin(User, User.id == AuditEvent.user_id)
        .filter(AuditEvent.organization_id == organization_id)
        .order_by(AuditEvent.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return AuditListResponse(
        items=[
            AuditRowResponse(
                id=event.id,
                created_at=event.created_at,
                action=event.action.replace("_", " "),
                resource_type=event.resource_type,
                actor_email=user.email if user else None,
            )
            for event, user in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/audit", response_model=AuditListResponse)
def list_audit(
    tenant: TenantContext = Depends(_require_org_admin_surface),
    db: Session = Depends(get_tenant_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> AuditListResponse:
    assert_org_admin_action(tenant, action="read", resource_type="audit", resource_org_id=tenant.organization_id)
    return _audit_rows(db, tenant.organization_id, page=page, page_size=page_size)


def _assert_browser_origin(request: Request) -> None:
    """CSRF-equivalent for Bearer SPA: require Origin/Referer on destructive org-admin calls."""
    settings = get_settings()
    if settings.app_env == "development":
        return
    if request.headers.get("X-Requested-With") != "AQREM":
        raise org_admin_error(
            code="CSRF_CHECK_FAILED",
            message="Missing confirmation header for this action.",
            status_code=403,
        )
    allowed = set(settings.cors_origins_list)
    origin = (request.headers.get("Origin") or "").strip()
    if not origin:
        referer = request.headers.get("Referer") or ""
        if referer:
            from urllib.parse import urlparse

            parsed = urlparse(referer)
            if parsed.scheme and parsed.netloc:
                origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin and (origin in allowed or "*" in allowed):
        return
    raise org_admin_error(
        code="ORIGIN_REQUIRED",
        message="This action must be requested from the admin web application (missing or invalid Origin).",
        status_code=403,
    )


@router.get("/audit/export")
def export_audit_csv(
    request: Request,
    tenant: TenantContext = Depends(_require_org_admin_surface),
    db: Session = Depends(get_tenant_db),
) -> Response:
    import csv
    import io

    assert_org_admin_action(tenant, action="read", resource_type="audit", resource_org_id=tenant.organization_id)
    rows = (
        db.query(AuditEvent, User)
        .outerjoin(User, User.id == AuditEvent.user_id)
        .filter(AuditEvent.organization_id == tenant.organization_id)
        .order_by(AuditEvent.created_at.desc())
        .limit(10_000)
        .all()
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["created_at", "actor_email", "action", "resource_type", "resource_id"])
    for event, user in rows:
        writer.writerow(
            [
                event.created_at.isoformat(),
                user.email if user else "",
                event.action,
                event.resource_type,
                event.resource_id or "",
            ]
        )
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="audit-log.csv"'},
    )


@router.delete("/audit-logs", response_model=AuditCleanupResponse)
@limiter.limit("6/hour")
def delete_audit_logs(
    request: Request,
    scope: str = Query(..., description="older_than_7d | older_than_30d | all"),
    tenant: TenantContext = Depends(_require_org_admin_surface),
    db: Session = Depends(get_tenant_db),
) -> AuditCleanupResponse:
    from app.services.audit.org_cleanup import ALLOWED_SCOPES, cleanup_org_audit_logs

    _assert_browser_origin(request)
    try:
        assert_org_admin_action(tenant, action="delete", resource_type="audit", resource_org_id=tenant.organization_id)
    except PolicyDenied as exc:
        raise org_admin_error(code=exc.code, message=exc.message, status_code=403) from exc
    if scope not in ALLOWED_SCOPES:
        raise org_admin_error(
            code="INVALID_SCOPE",
            message="Choose older than 7 days, older than 30 days, or all logs.",
            field="scope",
            status_code=400,
        )
    try:
        deleted = cleanup_org_audit_logs(
            db,
            organization_id=tenant.organization_id,
            admin_user_id=tenant.user_id,
            scope=scope,
        )
    except ValueError as exc:
        if str(exc) == "INVALID_SCOPE":
            raise org_admin_error(code="INVALID_SCOPE", message="Invalid cleanup scope.", field="scope") from exc
        raise
    db.commit()
    return AuditCleanupResponse(deleted_count=deleted, scope=scope)


@router.get("/telemetry-schema")
def telemetry_schema(
    tenant: TenantContext = Depends(_require_org_admin_surface),
) -> dict:
    assert_org_admin_action(
        tenant,
        action="read",
        resource_type="telemetry_schema",
        resource_org_id=tenant.organization_id,
    )
    return {
        "title": "What Azelos can see",
        "description": "Only these content-free fields may be sent to the master console.",
        "fields": TELEMETRY_FIELD_CATALOG,
    }


@router.get("/chat-sharing")
def get_chat_sharing(
    tenant: TenantContext = Depends(_require_org_admin_surface),
    control_db: Session = Depends(get_db),
) -> dict:
    org = control_db.get(Organization, tenant.organization_id)
    if org is None:
        raise org_admin_error(code="NOT_FOUND", message="Organization not found", status_code=404)
    return {"enabled": bool(org.chat_shares_enabled), "default_ttl_days": int(org.chat_share_ttl_days or 7)}


@router.put("/chat-sharing")
def update_chat_sharing(
    payload: dict,
    tenant: TenantContext = Depends(_require_org_admin_surface),
    control_db: Session = Depends(get_db),
    tenant_db: Session = Depends(get_tenant_db),
) -> dict:
    org = control_db.get(Organization, tenant.organization_id)
    if org is None:
        raise org_admin_error(code="NOT_FOUND", message="Organization not found", status_code=404)
    before = bool(org.chat_shares_enabled)
    if "enabled" in payload:
        org.chat_shares_enabled = bool(payload["enabled"])
    if "default_ttl_days" in payload:
        org.chat_share_ttl_days = max(1, min(int(payload["default_ttl_days"]), 90))
    record_audit(
        tenant_db,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        action="chat_sharing_updated",
        resource_type="organization",
        resource_id=str(org.id),
        metadata={"before_enabled": before, "after_enabled": org.chat_shares_enabled, "ttl_days": org.chat_share_ttl_days},
    )
    control_db.commit()
    tenant_db.commit()
    return {"enabled": org.chat_shares_enabled, "default_ttl_days": org.chat_share_ttl_days}


@router.post("/members/{membership_id}/password-reset", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def admin_trigger_password_reset(
    membership_id: UUID,
    tenant: TenantContext = Depends(_require_org_admin_surface),
    control_db: Session = Depends(get_db),
    tenant_db: Session = Depends(get_tenant_db),
) -> Response:
    from app.services.auth.password_reset import request_password_reset

    membership = control_db.get(OrganizationMembership, membership_id)
    if membership is None or membership.organization_id != tenant.organization_id:
        raise org_admin_error(code="NOT_FOUND", message="Member not found", status_code=404)
    user = control_db.get(User, membership.user_id)
    if user is None:
        raise org_admin_error(code="NOT_FOUND", message="Member not found", status_code=404)
    request_password_reset(control_db, email=user.email)
    record_audit(
        tenant_db,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        action="member_password_reset_requested",
        resource_type="user",
        resource_id=str(user.id),
        metadata={},
    )
    control_db.commit()
    tenant_db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _tenant_storage_response(cfg) -> TenantStorageResponse:
    from app.services.setup_checklist import tenant_database_setup_complete

    return TenantStorageResponse(
        storage_mode=cfg.storage_mode,
        connection_method=cfg.connection_method,
        status=cfg.status,
        host=cfg.host,
        port=cfg.port,
        database_name=cfg.database_name,
        schema_name=cfg.schema_name,
        ssl_mode=cfg.ssl_mode,
        username=cfg.username,
        has_credentials=bool(cfg.secret_reference),
        schema_version=cfg.schema_version,
        last_health_status=cfg.last_health_status,
        last_health_summary=cfg.last_health_summary,
        last_latency_ms=cfg.last_latency_ms,
        last_health_check_at=cfg.last_health_check_at.isoformat() if cfg.last_health_check_at else None,
        paused=cfg.paused,
        setup_validated_at=cfg.setup_validated_at.isoformat() if cfg.setup_validated_at else None,
        setup_complete=tenant_database_setup_complete(cfg),
    )


@router.get("/data-storage", response_model=TenantStorageResponse)
def get_data_storage(
    tenant: TenantContext = Depends(_require_org_admin_surface),
    control_db: Session = Depends(get_db),
) -> TenantStorageResponse:
    from app.tenant_store.resolver import ensure_managed_config

    cfg = ensure_managed_config(control_db, tenant.organization_id)
    return _tenant_storage_response(cfg)


@router.post("/data-storage/preflight", response_model=PreflightReportResponse)
def preflight_data_storage(
    payload: TenantStorageConfigureRequest,
    tenant: TenantContext = Depends(_require_org_admin_surface),
    control_db: Session = Depends(get_db),
) -> PreflightReportResponse:
    from app.schemas.tenant_storage import PreflightCheckResponse
    from app.tenant_store.preflight import run_preflight
    from app.tenant_store.setup_health import validate_managed_colocated

    if payload.storage_mode != "customer_postgres":
        ok, summary, latency = validate_managed_colocated(tenant.organization_id)
        return PreflightReportResponse(
            ok=ok,
            latency_ms=latency,
            checks=[
                PreflightCheckResponse(
                    id="managed",
                    title="AQREM-managed PostgreSQL",
                    status="pass" if ok else "fail",
                    detail=summary,
                )
            ],
        )
    if not payload.password or not payload.host or not payload.database_name or not payload.username:
        return PreflightReportResponse(
            ok=False,
            checks=[
                PreflightCheckResponse(
                    id="fields",
                    title="Connection details",
                    status="fail",
                    detail="Enter host, database name, username, and password before running preflight.",
                )
            ],
        )
    report = run_preflight(
        host=payload.host,
        port=payload.port,
        database_name=payload.database_name,
        username=payload.username,
        password=payload.password,
        ssl_mode=payload.ssl_mode,
        connection_method=payload.connection_method,
        schema_name=payload.schema_name,
    )
    return PreflightReportResponse(
        ok=report.ok,
        latency_ms=report.latency_ms,
        checks=[PreflightCheckResponse(id=c.id, title=c.title, status=c.status, detail=c.detail) for c in report.checks],
    )


@router.put("/data-storage", response_model=TenantStorageResponse)
def configure_data_storage(
    payload: TenantStorageConfigureRequest,
    tenant: TenantContext = Depends(_require_org_admin_surface),
    control_db: Session = Depends(get_db),
) -> TenantStorageResponse:
    from app.audit.service import record_audit
    from app.models.tenant_data_store import TenantDataStoreConfig
    from app.tenant_store.migrations import migrate_tenant_engine
    from app.tenant_store.pool import tenant_pool_manager
    from app.tenant_store.preflight import run_preflight
    from app.tenant_store.resolver import (
        CUSTOMER_POSTGRES,
        MANAGED_COLOCATED,
        build_database_url,
        default_secret_reference,
        ensure_managed_config,
    )
    from app.tenant_store.secrets import default_secret_store
    from app.tenant_store.setup_health import validate_managed_colocated

    cfg = ensure_managed_config(control_db, tenant.organization_id)
    before_mode = cfg.storage_mode
    now = datetime.now(UTC)

    try:
        if payload.storage_mode == MANAGED_COLOCATED:
            ok, summary, latency = validate_managed_colocated(tenant.organization_id)
            if not ok:
                raise org_admin_error(
                    code="MANAGED_VALIDATION_FAILED",
                    message=summary or "AQREM-managed PostgreSQL could not be validated.",
                )
            from app.core.config import get_settings

            settings = get_settings()
            engine = tenant_pool_manager.get_engine(str(tenant.organization_id), settings.database_url)
            migrate_tenant_engine(engine)
            cfg.storage_mode = MANAGED_COLOCATED
            cfg.connection_method = "managed"
            cfg.host = None
            cfg.port = None
            cfg.database_name = None
            cfg.username = None
            cfg.secret_reference = None
            cfg.status = "active"
            cfg.last_health_check_at = now
            cfg.last_health_status = "healthy"
            cfg.last_health_summary = summary
            cfg.last_latency_ms = latency
            cfg.setup_validated_at = now
        elif payload.storage_mode == CUSTOMER_POSTGRES:
            secrets = default_secret_store()
            ref = cfg.secret_reference or default_secret_reference(tenant.organization_id)
            password = payload.password or secrets.get(ref)
            if not password:
                raise org_admin_error(
                    code="PASSWORD_REQUIRED",
                    message="Password is required for your database.",
                    field="password",
                )
            report = run_preflight(
                host=payload.host or "",
                port=payload.port,
                database_name=payload.database_name or "",
                username=payload.username or "",
                password=password,
                ssl_mode=payload.ssl_mode,
                connection_method=payload.connection_method,
            )
            if not report.ok:
                raise org_admin_error(
                    code="PREFLIGHT_FAILED",
                    message="Preflight did not pass. Fix the issues listed in the preflight results and try again.",
                )
            if payload.password:
                secrets.put(ref, payload.password)
            cfg.storage_mode = CUSTOMER_POSTGRES
            cfg.connection_method = payload.connection_method
            cfg.host = payload.host
            cfg.port = payload.port
            cfg.database_name = payload.database_name
            cfg.schema_name = payload.schema_name
            cfg.ssl_mode = payload.ssl_mode
            cfg.username = payload.username
            cfg.secret_reference = ref
            cfg.status = "active"
            cfg.last_health_check_at = now
            cfg.last_health_status = "healthy"
            cfg.last_health_summary = "Preflight passed."
            cfg.last_latency_ms = report.latency_ms
            url = build_database_url(cfg, default_secret_store())
            engine = tenant_pool_manager.get_engine(str(tenant.organization_id), url)
            migrate_tenant_engine(engine)
            cfg.setup_validated_at = now
        else:
            raise org_admin_error(code="INVALID_MODE", message="Choose managed or customer PostgreSQL.", field="storage_mode")
    except HTTPException:
        control_db.rollback()
        raise
    except Exception as exc:
        control_db.rollback()
        raise org_admin_error(
            code="STORAGE_CONFIGURE_FAILED",
            message="Database configuration could not be saved. Your previous settings were kept.",
        ) from exc

    control_db.flush()
    record_audit(
        control_db,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        action="tenant_storage_configured",
        resource_type="tenant_data_store",
        resource_id=str(cfg.id),
        metadata={"before_mode": before_mode, "after_mode": cfg.storage_mode, "connection_method": cfg.connection_method},
    )
    control_db.commit()
    return _tenant_storage_response(cfg)


@router.post("/data-storage/refresh-health", response_model=TenantStorageResponse)
def refresh_data_storage_health(
    tenant: TenantContext = Depends(_require_org_admin_surface),
    control_db: Session = Depends(get_db),
) -> TenantStorageResponse:
    from app.tenant_store.resolver import ensure_managed_config
    from app.tenant_store.setup_health import refresh_config_health

    cfg = ensure_managed_config(control_db, tenant.organization_id)
    if cfg.setup_validated_at is None:
        raise org_admin_error(
            code="NOT_CONFIGURED",
            message="Activate a database mode before refreshing health.",
        )
    ok, summary, latency = refresh_config_health(cfg)
    now = datetime.now(UTC)
    cfg.last_health_check_at = now
    cfg.last_health_status = "healthy" if ok else "failed"
    cfg.last_health_summary = summary
    if latency is not None:
        cfg.last_latency_ms = latency
    control_db.commit()
    if not ok:
        raise org_admin_error(code="HEALTH_CHECK_FAILED", message=summary)
    return _tenant_storage_response(cfg)


@router.post("/employee-link/copied", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def employee_link_copied(
    tenant: TenantContext = Depends(_require_org_admin_surface),
    db: Session = Depends(get_tenant_db),
    control_db: Session = Depends(get_db),
) -> Response:
    checklist = build_setup_checklist(db, organization_id=tenant.organization_id, control_db=control_db)
    if not checklist.get("employee_link_enabled"):
        raise org_admin_error(
            code="LINK_LOCKED",
            message="Configure employee access before sharing the assistant link.",
        )
    record_audit(
        db,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        action="employee_link_copied",
        resource_type="organization",
        resource_id=str(tenant.organization_id),
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/employee-join/pending")
def list_pending_joins(
    tenant: TenantContext = Depends(_require_org_admin_surface),
    control_db: Session = Depends(get_db),
) -> list[dict]:
    from app.models.employee_join import EmployeeJoinPending

    rows = (
        control_db.query(EmployeeJoinPending)
        .filter(
            EmployeeJoinPending.organization_id == tenant.organization_id,
            EmployeeJoinPending.status == "pending_approval",
        )
        .order_by(EmployeeJoinPending.created_at.asc())
        .all()
    )
    return [
        {
            "id": str(r.id),
            "email": r.email,
            "full_name": r.full_name,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.post("/employee-join/pending/{pending_id}/approve", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def approve_pending(
    pending_id: UUID,
    tenant: TenantContext = Depends(_require_org_admin_surface),
    control_db: Session = Depends(get_db),
) -> Response:
    from app.services.invitations.employee_join import approve_pending_join

    try:
        approve_pending_join(
            control_db,
            approver_user_id=tenant.user_id,
            organization_id=tenant.organization_id,
            pending_id=pending_id,
        )
    except ValueError as exc:
        raise org_admin_error(code="NOT_FOUND", message=str(exc)) from exc
    control_db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/employee-join/pending/{pending_id}/reject", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def reject_pending(
    pending_id: UUID,
    tenant: TenantContext = Depends(_require_org_admin_surface),
    control_db: Session = Depends(get_db),
) -> Response:
    from app.services.invitations.employee_join import reject_pending_join

    try:
        reject_pending_join(
            control_db,
            approver_user_id=tenant.user_id,
            organization_id=tenant.organization_id,
            pending_id=pending_id,
        )
    except ValueError as exc:
        raise org_admin_error(code="NOT_FOUND", message=str(exc)) from exc
    control_db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
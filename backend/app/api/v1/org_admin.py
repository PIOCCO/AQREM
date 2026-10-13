"""Client organization admin console (private assistant dashboard)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.audit.service import record_audit
from app.core.config import get_settings
from app.core.dependencies import require_org_admin
from app.core.org_admin_errors import org_admin_error
from app.core.rate_limit import limiter
from app.core.roles import Role
from app.core.security import decode_access_token
from app.core.tenant import TenantContext
from app.db.session import get_db
from app.models.client_admin import ClientCredentialMetadata, ClientDocument
from app.models.enums import EvidenceScope, SourceType, SyncJobStatus
from app.models.invitation import UserInvitation
from app.models.organization import Organization, OrganizationMembership, User
from app.models.project import Project
from app.models.source import Source, SourceSyncJob
from app.models.audit import AuditEvent
from app.schemas.org_admin import (
    AuditRowResponse,
    DocumentListResponse,
    DocumentRowResponse,
    MemberInviteRequest,
    MemberRow,
    ModelTokenResponse,
    ModelTokenSaveRequest,
    UsageSummaryResponse,
)
from app.services.client_secrets.vault_store import get_client_secret_store
from app.services.licensing import LicenseDenied, assert_can_add_seat
from app.services.org_admin.malware_scan import scan_upload_content
from app.services.org_admin.policy import PolicyDenied, assert_org_admin_action
from app.services.platform_provisioning import provision_user_invitation
from app.services.setup_checklist import build_setup_checklist
from app.services.seat_usage import get_seat_usage
from app.services.storage.factory import get_blob_storage
from app.services.storage.path_utils import safe_blob_filename
from app.services.platform_provisioning import deactivate_membership
from app.services.telemetry_ingest import ingest_org_telemetry
from app.services.telemetry_schema import TELEMETRY_FIELD_CATALOG

router = APIRouter()


def _require_org_admin_surface(request: Request, tenant: TenantContext = Depends(require_org_admin)) -> TenantContext:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise org_admin_error(code="UNAUTHORIZED", message="Not authenticated", status_code=401)
    payload = decode_access_token(auth[7:])
    aud = payload.get("aud")
    if aud in {"aqrem-master", "aqrem-employee"}:
        raise org_admin_error(
            code="WRONG_AUDIENCE",
            message="This console requires an organization administrator session.",
            status_code=403,
        )
    settings = get_settings()
    if settings.app_env == "production" and aud != "aqrem-org-admin":
        raise org_admin_error(
            code="WRONG_AUDIENCE",
            message="Organization administrator token required.",
            status_code=403,
        )
    return tenant


def _sync_document_from_job(doc: ClientDocument, job: SourceSyncJob | None) -> None:
    if job is None:
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
        doc.failure_reason = (job.stats or {}).get("error") or "Indexing failed"


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


@router.get("/setup")
def get_setup_checklist(
    tenant: TenantContext = Depends(_require_org_admin_surface),
    db: Session = Depends(get_db),
) -> dict:
    assert_org_admin_action(tenant, action="read", resource_type="setup", resource_org_id=tenant.organization_id)
    return build_setup_checklist(db, organization_id=tenant.organization_id)


@router.get("/overview")
def org_admin_overview(
    tenant: TenantContext = Depends(_require_org_admin_surface),
    db: Session = Depends(get_db),
) -> dict:
    org = db.get(Organization, tenant.organization_id)
    checklist = build_setup_checklist(db, organization_id=tenant.organization_id)
    usage = get_seat_usage(db, org) if org else None
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
    db: Session = Depends(get_db),
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
    for doc in rows:
        job = db.get(SourceSyncJob, doc.sync_job_id) if doc.sync_job_id else None
        _sync_document_from_job(doc, job)
    db.commit()
    org_docs = db.query(ClientDocument).filter(ClientDocument.organization_id == tenant.organization_id)
    counts = {
        "total": total,
        "indexed": org_docs.filter(ClientDocument.status == "indexed").count(),
        "indexing": org_docs.filter(ClientDocument.status.in_(("uploading", "indexing"))).count(),
        "failed": org_docs.filter(ClientDocument.status == "failed").count(),
    }
    return DocumentListResponse(
        items=[
            DocumentRowResponse(
                id=r.id,
                file_name=r.file_name,
                size_bytes=r.size_bytes,
                content_type=r.content_type,
                status=r.status,
                index_progress=r.index_progress,
                failure_reason=r.failure_reason,
                created_at=r.created_at,
            )
            for r in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
        counts=counts,
    )


@router.post("/documents/upload")
@limiter.limit("20/minute")
async def upload_documents(
    request: Request,
    tenant: TenantContext = Depends(_require_org_admin_surface),
    db: Session = Depends(get_db),
    files: list[UploadFile] = File(...),
) -> dict:
    assert_org_admin_action(tenant, action="write", resource_type="document", resource_org_id=tenant.organization_id)
    settings = get_settings()
    source = _ensure_document_source(db, tenant)
    storage = get_blob_storage()
    created: list[str] = []
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
        storage.upload_bytes(blob_path, data, upload.content_type or "application/octet-stream")
        doc = ClientDocument(
            organization_id=tenant.organization_id,
            source_id=source.id,
            file_name=safe_name,
            content_type=upload.content_type or "application/octet-stream",
            size_bytes=len(data),
            blob_path=blob_path,
            status="uploading",
            index_progress=5,
            malware_scan_status=scan_status,
            content_hash=content_hash,
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
        created.append(str(doc.id))
        record_audit(
            db,
            organization_id=tenant.organization_id,
            user_id=tenant.user_id,
            action="client_document_uploaded",
            resource_type="client_document",
            resource_id=str(doc.id),
            metadata={"size_bytes": len(data), "content_type": doc.content_type},
        )
        try:
            from worker.app.tasks.ingestion import enqueue_source_sync

            enqueue_source_sync(str(job.id))
        except Exception:
            pass
    ingest_org_telemetry(
        db,
        organization_id=tenant.organization_id,
        event_type="document.indexing_job_completed",
        payload={"indexed_count": len(created), "failed_count": 0, "indexing_count": len(created)},
    )
    db.commit()
    return {"document_ids": created}


@router.delete("/documents/{document_id}", status_code=204)
def remove_document(
    document_id: UUID,
    tenant: TenantContext = Depends(_require_org_admin_surface),
    db: Session = Depends(get_db),
) -> None:
    assert_org_admin_action(tenant, action="delete", resource_type="document", resource_org_id=tenant.organization_id)
    doc = db.get(ClientDocument, document_id)
    if doc is None or doc.organization_id != tenant.organization_id:
        raise org_admin_error(code="NOT_FOUND", message="Document not found.", status_code=404)
    record_audit(
        db,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        action="client_document_removed",
        resource_type="client_document",
        resource_id=str(doc.id),
        metadata={"size_bytes": doc.size_bytes},
    )
    db.delete(doc)
    db.commit()


@router.post("/documents/{document_id}/retry")
def retry_document(
    document_id: UUID,
    tenant: TenantContext = Depends(_require_org_admin_surface),
    db: Session = Depends(get_db),
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
    doc.failure_reason = None
    db.commit()
    return {"job_id": str(job.id)}


@router.get("/model-token", response_model=ModelTokenResponse)
def get_model_token(
    tenant: TenantContext = Depends(_require_org_admin_surface),
    db: Session = Depends(get_db),
) -> ModelTokenResponse:
    assert_org_admin_action(tenant, action="read", resource_type="credential", resource_org_id=tenant.organization_id)
    cred = db.query(ClientCredentialMetadata).filter(ClientCredentialMetadata.organization_id == tenant.organization_id).first()
    if cred is None:
        return ModelTokenResponse(
            masked_value="Not configured",
            status="not_configured",
            expires_at=None,
            last_rotated_at=None,
            last_test_at=None,
            last_test_status=None,
        )
    warning = None
    if cred.expires_at:
        days = (cred.expires_at - datetime.now(UTC)).days
        if days <= 7:
            warning = days
        elif days <= 30:
            warning = days
    return ModelTokenResponse(
        masked_value=cred.masked_hint,
        status=cred.status,
        expires_at=cred.expires_at,
        last_rotated_at=cred.last_rotated_at,
        last_test_at=cred.last_test_at,
        last_test_status=cred.last_test_status,
        expiry_warning_days=warning,
    )


@router.put("/model-token", response_model=ModelTokenResponse)
@limiter.limit("10/minute")
def save_model_token(
    request: Request,
    payload: ModelTokenSaveRequest,
    tenant: TenantContext = Depends(_require_org_admin_surface),
    db: Session = Depends(get_db),
) -> ModelTokenResponse:
    assert_org_admin_action(tenant, action="write", resource_type="credential", resource_org_id=tenant.organization_id)
    store = get_client_secret_store()
    vault_ref = store.write_model_token(tenant.organization_id, payload.token.strip())
    hint = f"****{payload.token.strip()[-4:]}" if len(payload.token.strip()) >= 4 else "****"
    cred = db.query(ClientCredentialMetadata).filter(ClientCredentialMetadata.organization_id == tenant.organization_id).first()
    now = datetime.now(UTC)
    expires = now + timedelta(days=365)
    if cred is None:
        cred = ClientCredentialMetadata(
            organization_id=tenant.organization_id,
            vault_secret_name=vault_ref,
            masked_hint=hint,
            status="connected",
            expires_at=expires,
            last_rotated_at=now,
        )
        db.add(cred)
    else:
        cred.vault_secret_name = vault_ref
        cred.masked_hint = hint
        cred.status = "connected"
        cred.last_rotated_at = now
        cred.expires_at = expires
    record_audit(
        db,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        action="model_token_configured",
        resource_type="credential",
        resource_id=str(cred.id),
        metadata={"status": cred.status},
    )
    ingest_org_telemetry(
        db,
        organization_id=tenant.organization_id,
        event_type="credential.expiry_metadata_updated",
        payload={"expires_at_iso": expires.date().isoformat(), "status": cred.status},
    )
    db.commit()
    return get_model_token(tenant=tenant, db=db)


@router.post("/model-token/test")
@limiter.limit("10/minute")
def test_model_token(
    request: Request,
    tenant: TenantContext = Depends(_require_org_admin_surface),
    db: Session = Depends(get_db),
) -> dict:
    cred = db.query(ClientCredentialMetadata).filter(ClientCredentialMetadata.organization_id == tenant.organization_id).first()
    if cred is None:
        raise org_admin_error(code="NOT_CONFIGURED", message="Configure a model token first.", field="token")
    ok, message = get_client_secret_store().test_model_token(tenant.organization_id)
    cred.last_test_at = datetime.now(UTC)
    cred.last_test_status = "success" if ok else "failed"
    record_audit(
        db,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        action="model_token_tested",
        resource_type="credential",
        resource_id=str(cred.id),
        metadata={"result": cred.last_test_status},
    )
    db.commit()
    return {"success": ok, "message": message}


@router.post("/model-token/rotate", response_model=ModelTokenResponse)
def rotate_model_token(
    tenant: TenantContext = Depends(_require_org_admin_surface),
    db: Session = Depends(get_db),
) -> ModelTokenResponse:
    raise org_admin_error(
        code="ROTATION_REQUIRES_NEW_TOKEN",
        message="Paste a new token in the form and save to rotate. The previous secret is replaced in Key Vault.",
        field="token",
    )


@router.get("/members", response_model=list[MemberRow])
def list_members(
    tenant: TenantContext = Depends(_require_org_admin_surface),
    db: Session = Depends(get_db),
) -> list[MemberRow]:
    assert_org_admin_action(tenant, action="read", resource_type="member", resource_org_id=tenant.organization_id)
    rows = (
        db.query(OrganizationMembership, User)
        .join(User, User.id == OrganizationMembership.user_id)
        .filter(OrganizationMembership.organization_id == tenant.organization_id)
        .all()
    )
    return [
        MemberRow(
            membership_id=m.id,
            user_id=u.id,
            email=u.email,
            full_name=u.full_name,
            role=m.role,
            is_active=m.is_active and u.is_active,
        )
        for m, u in rows
    ]


@router.post("/members/invite", status_code=201)
@limiter.limit("30/minute")
def invite_member(
    request: Request,
    payload: MemberInviteRequest,
    tenant: TenantContext = Depends(_require_org_admin_surface),
    db: Session = Depends(get_db),
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
        role = Role(payload.role.upper())
    except ValueError as exc:
        raise org_admin_error(code="INVALID_ROLE", message="Choose Organization admin, Editor, or Viewer.", field="role") from exc
    if payload.role.upper() == "PLATFORM_ADMIN":
        raise org_admin_error(code="INVALID_ROLE", message="Invalid role.", field="role")
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
    return {"invitation_setup_path": f"/accept-invite?token={raw_token}", "expires_at": expires_at.isoformat()}


@router.post("/members/{membership_id}/deactivate", status_code=204)
def deactivate_org_member(
    membership_id: UUID,
    tenant: TenantContext = Depends(_require_org_admin_surface),
    db: Session = Depends(get_db),
) -> None:
    assert_org_admin_action(tenant, action="write", resource_type="member", resource_org_id=tenant.organization_id)
    membership = db.get(OrganizationMembership, membership_id)
    if membership is None or membership.organization_id != tenant.organization_id:
        raise org_admin_error(code="NOT_FOUND", message="Member not found.", status_code=404)
    if membership.user_id == tenant.user_id:
        raise org_admin_error(code="INVALID_STATE", message="You cannot deactivate your own membership.", status_code=400)
    deactivate_membership(db, admin_user_id=tenant.user_id, membership=membership)
    db.commit()


@router.get("/usage", response_model=UsageSummaryResponse)
def usage_summary(
    tenant: TenantContext = Depends(_require_org_admin_surface),
    db: Session = Depends(get_db),
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


@router.get("/audit", response_model=list[AuditRowResponse])
def list_audit(
    tenant: TenantContext = Depends(_require_org_admin_surface),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[AuditRowResponse]:
    assert_org_admin_action(tenant, action="read", resource_type="audit", resource_org_id=tenant.organization_id)
    rows = (
        db.query(AuditEvent, User)
        .outerjoin(User, User.id == AuditEvent.user_id)
        .filter(AuditEvent.organization_id == tenant.organization_id)
        .order_by(AuditEvent.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        AuditRowResponse(
            id=event.id,
            created_at=event.created_at,
            action=event.action.replace("_", " "),
            resource_type=event.resource_type,
            actor_email=user.email if user else None,
        )
        for event, user in rows
    ]


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


@router.post("/employee-link/copied", status_code=204)
def employee_link_copied(
    tenant: TenantContext = Depends(_require_org_admin_surface),
    db: Session = Depends(get_db),
) -> None:
    checklist = build_setup_checklist(db, organization_id=tenant.organization_id)
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

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.audit.service import record_audit
from app.core.config import get_settings
from app.core.dependencies import get_tenant_context, require_role
from app.core.roles import Role
from app.core.tenant import TenantContext
from app.db.session import get_db
from app.models.enums import SourceType, SyncJobStatus
from app.models.source import GitHubRepoConfig, Source, SourceSyncJob
from app.schemas.source import GitHubRepoConnectRequest, SourceCreate, SourceResponse, SyncJobResponse
from app.services.storage.factory import get_blob_storage

router = APIRouter()


def _validate_extension(filename: str) -> None:
    settings = get_settings()
    suffixes = {".tar.gz"}
    lower = filename.lower()
    ext = Path(lower).suffix
    if lower.endswith(".tar.gz"):
        ext = ".tar.gz"
    if ext not in settings.allowed_extensions_set:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"File type not allowed: {ext}")


@router.get("", response_model=list[SourceResponse])
def list_sources(
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> list[Source]:
    return db.query(Source).filter(Source.organization_id == tenant.organization_id).all()


@router.post("", response_model=SourceResponse)
def create_source(
    payload: SourceCreate,
    tenant: TenantContext = Depends(require_role(Role.EDITOR)),
    db: Session = Depends(get_db),
) -> Source:
    source = Source(
        organization_id=tenant.organization_id,
        project_id=payload.project_id,
        name=payload.name,
        source_type=payload.source_type.value,
        scope=payload.scope.value,
        config=payload.config,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    record_audit(
        db,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        action="source_connected",
        resource_type="source",
        resource_id=str(source.id),
    )
    db.commit()
    return source


@router.post("/{source_id}/files", response_model=SyncJobResponse)
async def upload_files(
    source_id: UUID,
    files: list[UploadFile] = File(...),
    tenant: TenantContext = Depends(require_role(Role.EDITOR)),
    db: Session = Depends(get_db),
) -> SourceSyncJob:
    settings = get_settings()
    source = db.get(Source, source_id)
    if source is None or source.organization_id != tenant.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")

    storage = get_blob_storage()
    uploaded_paths: list[str] = []
    for upload in files:
        _validate_extension(upload.filename or "upload.bin")
        data = await upload.read()
        if len(data) > settings.max_upload_bytes:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large")
        blob_path = f"{tenant.organization_id}/{source.id}/{upload.filename}"
        storage.upload_bytes(blob_path, data, upload.content_type or "application/octet-stream")
        uploaded_paths.append(blob_path)

    job = SourceSyncJob(
        organization_id=tenant.organization_id,
        source_id=source.id,
        status=SyncJobStatus.QUEUED.value,
        stats={"uploaded_blobs": uploaded_paths},
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    from worker.app.tasks.ingestion import enqueue_source_sync

    enqueue_source_sync(str(job.id))
    return job


@router.post("/{source_id}/sync", response_model=SyncJobResponse)
def trigger_sync(
    source_id: UUID,
    tenant: TenantContext = Depends(require_role(Role.EDITOR)),
    db: Session = Depends(get_db),
) -> SourceSyncJob:
    source = db.get(Source, source_id)
    if source is None or source.organization_id != tenant.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")

    job = SourceSyncJob(
        organization_id=tenant.organization_id,
        source_id=source.id,
        status=SyncJobStatus.QUEUED.value,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    from worker.app.tasks.ingestion import enqueue_source_sync

    enqueue_source_sync(str(job.id))
    return job


@router.post("/github/connect-repo", response_model=SourceResponse)
def connect_github_repo(
    payload: GitHubRepoConnectRequest,
    tenant: TenantContext = Depends(require_role(Role.EDITOR)),
    db: Session = Depends(get_db),
) -> Source:
    source = db.get(Source, payload.source_id)
    if source is None or source.organization_id != tenant.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    if source.source_type != SourceType.GITHUB.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Source is not GitHub type")

    config = dict(source.config)
    if payload.access_token:
        config["github_token_ref"] = "inline-dev-token"
        config["github_token"] = payload.access_token

    source.config = config
    existing = db.query(GitHubRepoConfig).filter(GitHubRepoConfig.source_id == source.id).first()
    if existing:
        existing.repository_full_name = payload.repository_full_name
        existing.default_branch = payload.branch
    else:
        db.add(
            GitHubRepoConfig(
                organization_id=tenant.organization_id,
                source_id=source.id,
                repository_full_name=payload.repository_full_name,
                default_branch=payload.branch,
            )
        )
    db.commit()
    db.refresh(source)
    return source


@router.get("/jobs/{job_id}", response_model=SyncJobResponse)
def get_job(
    job_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> SourceSyncJob:
    job = db.get(SourceSyncJob, job_id)
    if job is None or job.organization_id != tenant.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job

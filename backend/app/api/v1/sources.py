from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.dependencies import get_tenant_context, require_role
from app.core.roles import Role
from app.core.tenant import TenantContext
from app.db.session import get_db
from app.models.enums import SourceType, SyncJobStatus
from app.models.source import Source, SourceSyncJob
from app.schemas.source import GitHubRepoConnectRequest, SourceCreate, SourceResponse, SyncJobResponse
from app.services.sources.service import connect_github_to_source, create_source_record
from app.services.storage.factory import get_blob_storage
from app.services.storage.path_utils import safe_blob_filename

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
    project_id: UUID | None = Query(default=None),
) -> list[Source]:
    query = db.query(Source).filter(Source.organization_id == tenant.organization_id)
    if project_id:
        query = query.filter(
            (Source.project_id == project_id) | (Source.project_id.is_(None))
        )
    return query.order_by(Source.created_at.desc()).all()


@router.post("", response_model=SourceResponse)
def create_source(
    payload: SourceCreate,
    tenant: TenantContext = Depends(require_role(Role.EDITOR)),
    db: Session = Depends(get_db),
) -> Source:
    return create_source_record(db, tenant, payload)


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
        raw_name = upload.filename or "upload.bin"
        _validate_extension(raw_name)
        try:
            safe_name = safe_blob_filename(raw_name)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid filename") from exc
        data = await upload.read()
        if len(data) > settings.max_upload_bytes:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large")
        blob_path = f"{tenant.organization_id}/{source.id}/{safe_name}"
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
    try:
        return connect_github_to_source(db, tenant, source, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{source_id}/jobs", response_model=list[SyncJobResponse])
def list_source_jobs(
    source_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
    limit: int = Query(default=10, ge=1, le=50),
) -> list[SourceSyncJob]:
    source = db.get(Source, source_id)
    if source is None or source.organization_id != tenant.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    return (
        db.query(SourceSyncJob)
        .filter(SourceSyncJob.source_id == source_id)
        .order_by(SourceSyncJob.created_at.desc())
        .limit(limit)
        .all()
    )


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

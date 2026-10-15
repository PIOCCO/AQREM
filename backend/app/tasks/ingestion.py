import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID

logger = logging.getLogger(__name__)

from sqlalchemy.orm import Session

from app.audit.service import record_audit
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.enums import SourceType, SyncJobStatus
from app.models.source import GitHubRepoConfig, Source, SourceSyncJob
from app.services.github.client import GitHubClient, GitHubRepoRef, extract_archive_bytes
from app.services.ingestion.document_progress import (
    STAGE_CHUNKING,
    STAGE_EMBEDDING,
    STAGE_INDEXED,
    STAGE_PARSING,
    STAGE_QUEUED,
    STAGE_READING,
    STAGE_WRITING,
    load_document_for_job,
    mark_document_empty,
    mark_document_failed,
    mark_document_progress,
)
from app.services.ingestion.indexer import FilePayload, index_files
from app.services.storage.factory import get_blob_storage
from app.tenant_store.resolver import open_tenant_session
from app.celery_app import celery_app


def _validate_blob_paths_for_org(blob_paths: list, organization_id: UUID) -> None:
    prefix = f"{organization_id}/"
    for raw in blob_paths:
        if not isinstance(raw, str):
            raise ValueError("invalid blob reference")
        if ".." in raw or "\0" in raw:
            raise ValueError("invalid blob path")
        if not raw.startswith(prefix):
            raise ValueError("blob path outside organization scope")


def _touch_job(db: Session, job: SourceSyncJob) -> None:
    job.progress_updated_at = datetime.now(UTC)


def _fail_job(db: Session, job: SourceSyncJob, message: str, doc=None) -> dict:
    job.status = SyncJobStatus.FAILED.value
    job.error_message = message[:500]
    job.completed_at = datetime.now(UTC)
    _touch_job(db, job)
    if doc is not None:
        mark_document_failed(db, doc, message)
    db.commit()
    return {"error": message}


def enqueue_source_sync(job_id: str, organization_id: str) -> None:
    run_source_sync.delay(job_id, organization_id)


@celery_app.task(name="worker.app.tasks.ingestion.run_source_sync")
def run_source_sync(job_id: str, organization_id: str) -> dict:
    logger.info("run_source_sync started job=%s org=%s", job_id, organization_id)
    control: Session = SessionLocal()
    db: Session | None = None
    doc = None
    try:
        org_uuid = UUID(organization_id)
        db = open_tenant_session(control, org_uuid)
        job = db.get(SourceSyncJob, UUID(job_id))
        if job is None:
            return {"error": "job_not_found"}
        doc = load_document_for_job(db, job.stats)
        if doc is not None:
            mark_document_progress(db, doc, stage=STAGE_QUEUED, status="indexing")
            db.commit()

        if job.organization_id != org_uuid:
            return _fail_job(db, job, "organization_id does not match sync job", doc)
        source = db.get(Source, job.source_id)
        if source is None:
            return _fail_job(db, job, "Source not found", doc)
        if source.organization_id != org_uuid:
            return _fail_job(db, job, "source organization mismatch", doc)

        files: list[FilePayload] = []
        pending_blobs: list[str] = []
        if source.source_type == SourceType.GITHUB.value:
            cfg = db.query(GitHubRepoConfig).filter(GitHubRepoConfig.source_id == source.id).first()
            if cfg is None:
                raise ValueError("GitHub repository not configured")
            owner, repo = cfg.repository_full_name.split("/", 1)
            token = source.config.get("github_token")
            client = GitHubClient(token=token)
            files = asyncio.run(
                client.fetch_repo_archive(
                    GitHubRepoRef(owner=owner, repo=repo, branch=cfg.default_branch, token=token)
                )
            )
            cfg.last_indexed_commit = files[0].commit_hash if files else cfg.last_indexed_commit
        else:
            pending_blobs = list(job.stats.get("uploaded_blobs") or [])
            if pending_blobs:
                _validate_blob_paths_for_org(pending_blobs, org_uuid)

        job.status = SyncJobStatus.RUNNING.value
        job.started_at = datetime.now(UTC)
        _touch_job(db, job)
        if doc is not None:
            mark_document_progress(db, doc, stage=STAGE_READING, status="indexing")
        db.commit()

        if source.source_type == SourceType.GITHUB.value:
            pass
        else:
            storage = get_blob_storage()
            blobs = pending_blobs
            if not blobs and source.config.get("demo_path"):
                settings = get_settings()
                if settings.app_env != "development":
                    raise ValueError("demo_path indexing is only allowed in development")
                from pathlib import Path

                demo_root = Path(source.config["demo_path"])
                for path in demo_root.rglob("*"):
                    if path.is_file():
                        rel = str(path.relative_to(demo_root))
                        files.append(FilePayload(relative_path=rel, data=path.read_bytes()))
            for blob_path in blobs:
                raw = storage.download_bytes(blob_path)
                if len(raw) == 0:
                    if doc is not None:
                        mark_document_empty(db, doc)
                    job.status = SyncJobStatus.COMPLETED.value
                    job.completed_at = datetime.now(UTC)
                    job.stats = {**(job.stats or {}), "indexed_chunks": 0, "skipped_files": 1}
                    _touch_job(db, job)
                    db.commit()
                    return job.stats
                name = blob_path.split("/")[-1]
                files.extend(extract_archive_bytes(name, raw))

        if not files:
            if doc is not None:
                mark_document_failed(db, doc, "No indexable content in file.")
            return _fail_job(db, job, "No indexable content in file.", doc)

        stage_map = {
            "parsing": STAGE_PARSING,
            "chunking": STAGE_CHUNKING,
            "embedding": STAGE_EMBEDDING,
            "writing": STAGE_WRITING,
        }

        def on_progress(stage: str, processed: int, total: int | None) -> None:
            if doc is None:
                return
            mark_document_progress(
                db,
                doc,
                stage=stage_map.get(stage, stage),
                processed_units=processed,
                total_units=total,
                status="indexing",
            )
            _touch_job(db, job)
            db.commit()

        stats = asyncio.run(index_files(db, source=source, job=job, files=files, on_progress=on_progress))
        job.completed_at = datetime.now(UTC)
        _touch_job(db, job)
        chunk_count = int(stats.get("indexed_chunks") or 0)
        if doc is not None:
            if chunk_count == 0:
                mark_document_failed(db, doc, "No indexable text found in file.")
                job.status = SyncJobStatus.FAILED.value
                job.error_message = "No indexable text found in file."
            else:
                mark_document_progress(
                    db,
                    doc,
                    stage=STAGE_INDEXED,
                    status="indexed",
                    processed_units=chunk_count,
                    total_units=chunk_count,
                    indexed_chunk_count=chunk_count,
                )
        record_audit(
            db,
            organization_id=source.organization_id,
            user_id=None,
            action="source_indexed",
            resource_type="source",
            resource_id=str(source.id),
            metadata=stats,
        )
        db.commit()
        return stats
    except Exception as exc:  # noqa: BLE001
        if db is not None:
            db.rollback()
            job = db.get(SourceSyncJob, UUID(job_id))
            if job:
                safe_msg = str(exc).splitlines()[0][:500]
                job.status = SyncJobStatus.FAILED.value
                job.error_message = safe_msg
                job.completed_at = datetime.now(UTC)
                _touch_job(db, job)
                if doc is None:
                    doc = load_document_for_job(db, job.stats)
                if doc is not None:
                    mark_document_failed(db, doc, safe_msg)
                db.commit()
        safe_err = str(exc).splitlines()[0][:200]
        return {"error": safe_err}
    finally:
        if db is not None:
            db.close()
        control.close()

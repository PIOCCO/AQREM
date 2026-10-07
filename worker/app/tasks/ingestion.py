import asyncio
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.audit.service import record_audit
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.enums import SourceType, SyncJobStatus
from app.models.source import GitHubRepoConfig, Source, SourceSyncJob
from app.services.github.client import GitHubClient, GitHubRepoRef, extract_archive_bytes
from app.services.ingestion.indexer import FilePayload, index_files
from app.services.storage.factory import get_blob_storage
from worker.app.celery_app import celery_app


def enqueue_source_sync(job_id: str) -> None:
    run_source_sync.delay(job_id)


@celery_app.task(name="worker.app.tasks.ingestion.run_source_sync")
def run_source_sync(job_id: str) -> dict:
    db: Session = SessionLocal()
    try:
        job = db.get(SourceSyncJob, UUID(job_id))
        if job is None:
            return {"error": "job_not_found"}
        source = db.get(Source, job.source_id)
        if source is None:
            job.status = SyncJobStatus.FAILED.value
            job.error_message = "Source not found"
            db.commit()
            return {"error": "source_not_found"}

        job.status = SyncJobStatus.RUNNING.value
        job.started_at = datetime.now(UTC)
        db.commit()

        files: list[FilePayload] = []
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
            storage = get_blob_storage()
            blobs = job.stats.get("uploaded_blobs") or []
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
                name = blob_path.split("/")[-1]
                files.extend(extract_archive_bytes(name, raw))

        stats = asyncio.run(index_files(db, source=source, job=job, files=files))
        job.completed_at = datetime.now(UTC)
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
        db.rollback()
        job = db.get(SourceSyncJob, UUID(job_id))
        if job:
            job.status = SyncJobStatus.FAILED.value
            job.error_message = str(exc)[:2000]
            job.completed_at = datetime.now(UTC)
            db.commit()
        return {"error": str(exc)}
    finally:
        db.close()

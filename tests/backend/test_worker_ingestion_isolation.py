"""Celery ingestion task must not process cross-tenant job or blob payloads."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from app.models.enums import EvidenceScope, SourceType, SyncJobStatus
from app.models.organization import Organization
from app.models.project import Project
from app.models.source import Source, SourceSyncJob
from app.tasks.ingestion import (
    _validate_blob_paths_for_org,
    run_source_sync,
)


@pytest.fixture()
def worker_db(db_session: Session, monkeypatch):
    """Run worker task against the same DB transaction as API tests."""
    monkeypatch.setattr("app.tasks.ingestion.SessionLocal", lambda: db_session)
    monkeypatch.setattr("app.tasks.ingestion.open_tenant_session", lambda _control, _org_id: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)
    return db_session


def _org_with_folder_source(db: Session, slug: str) -> tuple[Organization, Source, SourceSyncJob]:
    org = Organization(name=slug, slug=slug, license_limit=5, is_active=True)
    db.add(org)
    db.flush()
    project = Project(organization_id=org.id, name="P")
    db.add(project)
    db.flush()
    source = Source(
        organization_id=org.id,
        project_id=project.id,
        name="Uploads",
        source_type=SourceType.FOLDER_ARCHIVE.value,
        scope=EvidenceScope.PROJECT.value,
        config={},
    )
    db.add(source)
    db.flush()
    job = SourceSyncJob(
        organization_id=org.id,
        source_id=source.id,
        status=SyncJobStatus.QUEUED.value,
        stats={"uploaded_blobs": [f"{org.id}/{source.id}/sample.txt"]},
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return org, source, job


def test_validate_blob_paths_rejects_foreign_prefix():
    org = uuid4()
    other = uuid4()
    _validate_blob_paths_for_org([f"{org}/src/file.txt"], org)
    with pytest.raises(ValueError, match="outside organization scope"):
        _validate_blob_paths_for_org([f"{other}/src/file.txt"], org)


def test_run_source_sync_rejects_wrong_organization_id(worker_db: Session):
    db_session = worker_db
    org_a, _source_a, job_a = _org_with_folder_source(db_session, f"worker-a-{uuid4().hex[:6]}")
    org_b, _, _ = _org_with_folder_source(db_session, f"worker-b-{uuid4().hex[:6]}")

    job_id = job_a.id
    result = run_source_sync(str(job_id), str(org_b.id))

    assert result.get("error") == "organization_id does not match sync job"
    job_row = db_session.get(SourceSyncJob, job_id)
    assert job_row is not None
    assert job_row.status == SyncJobStatus.FAILED.value
    assert "organization_id" in (job_row.error_message or "")


def test_run_source_sync_rejects_foreign_blob_prefix(worker_db: Session):
    db_session = worker_db
    org_a, source_a, job_a = _org_with_folder_source(db_session, f"worker-blob-a-{uuid4().hex[:6]}")
    org_b, source_b, _ = _org_with_folder_source(db_session, f"worker-blob-b-{uuid4().hex[:6]}")
    job_a.stats = {"uploaded_blobs": [f"{org_b.id}/{source_b.id}/evil.txt"]}
    db_session.commit()

    job_id = job_a.id
    result = run_source_sync(str(job_id), str(org_a.id))

    assert "organization scope" in (result.get("error") or "").lower()
    job_row = db_session.get(SourceSyncJob, job_id)
    assert job_row is not None
    assert job_row.status == SyncJobStatus.FAILED.value


def test_run_source_sync_job_not_found_returns_error(worker_db: Session):
    db_session = worker_db
    org, _, _ = _org_with_folder_source(db_session, f"worker-missing-{uuid4().hex[:6]}")
    missing = uuid4()
    result = run_source_sync(str(missing), str(org.id))
    assert result.get("error") == "job_not_found"

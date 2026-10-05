import asyncio
from pathlib import Path

import pytest

from app.models.enums import EvidenceScope, SourceType, SyncJobStatus
from app.models.organization import Organization
from app.models.project import Project
from app.models.source import Source, SourceSyncJob
from app.services.ingestion.indexer import FilePayload, index_files
from app.services.retrieval.service import RetrievalService


@pytest.mark.asyncio
async def test_demo_repo_indexes_encryption_evidence(db_session, demo_repo_path: str):
    org = Organization(name="Demo Org", slug="demo-org")
    db_session.add(org)
    db_session.flush()
    project = Project(organization_id=org.id, name="SaaS Platform")
    db_session.add(project)
    db_session.flush()

    source = Source(
        organization_id=org.id,
        project_id=project.id,
        name="Demo Repo",
        source_type=SourceType.FOLDER_ARCHIVE.value,
        scope=EvidenceScope.PROJECT.value,
    )
    db_session.add(source)
    db_session.flush()
    job = SourceSyncJob(
        organization_id=org.id,
        source_id=source.id,
        status=SyncJobStatus.RUNNING.value,
    )
    db_session.add(job)
    db_session.commit()

    files: list[FilePayload] = []
    root = Path(demo_repo_path)
    for path in root.rglob("*"):
        if path.is_file():
            files.append(FilePayload(relative_path=str(path.relative_to(root)), data=path.read_bytes()))

    stats = await index_files(db_session, source=source, job=job, files=files)
    assert stats["indexed_chunks"] > 0

    results = await RetrievalService(db_session).retrieve(
        organization_id=org.id,
        project_id=project.id,
        query="Do you encrypt customer data at rest?",
        limit=5,
    )
    assert results
    paths = {item.file_path for item in results}
    assert any("database.tf" in p or "architecture.md" in p or "storage.tf" in p for p in paths)
    assert any(item.line_start is not None for item in results if item.file_path.endswith(".tf"))

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.roles import Role
from app.core.security import create_access_token, hash_password
from app.models.enums import EvidenceScope, SourceType, SyncJobStatus
from app.models.evidence import EvidenceItem
from app.models.organization import Organization, OrganizationMembership, User
from app.models.project import Project
from app.models.source import Source, SourceSyncJob
from app.services.ingestion.indexer import FilePayload, index_files
from app.services.retrieval.service import RetrievalService


def _auth_headers(token: str, org_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}


@pytest.mark.asyncio
async def test_project_scope_isolation(db_session, demo_repo_path: str):
    org = Organization(name="Acme", slug="acme")
    db_session.add(org)
    db_session.flush()

    project_a = Project(organization_id=org.id, name="SaaS Platform")
    project_b = Project(organization_id=org.id, name="API Platform")
    db_session.add_all([project_a, project_b])
    db_session.flush()

    source_a = Source(
        organization_id=org.id,
        project_id=project_a.id,
        name="Repo A",
        source_type=SourceType.FOLDER_ARCHIVE.value,
        scope=EvidenceScope.PROJECT.value,
    )
    source_b = Source(
        organization_id=org.id,
        project_id=project_b.id,
        name="Repo B",
        source_type=SourceType.FOLDER_ARCHIVE.value,
        scope=EvidenceScope.PROJECT.value,
    )
    db_session.add_all([source_a, source_b])
    db_session.flush()
    assert source_a.id != source_b.id
    assert source_a.project_id == project_a.id
    assert source_b.project_id == project_b.id

    secret_a = FilePayload(
        relative_path="secrets/saas-only.txt",
        data=b"SaaS platform customer data encryption at rest with AES-256.",
    )
    secret_b = FilePayload(
        relative_path="secrets/api-only.txt",
        data=b"API platform uses dedicated HSM partition Z99.",
    )

    job_a = SourceSyncJob(
        organization_id=org.id, source_id=source_a.id, status=SyncJobStatus.RUNNING.value
    )
    job_b = SourceSyncJob(
        organization_id=org.id, source_id=source_b.id, status=SyncJobStatus.RUNNING.value
    )
    db_session.add_all([job_a, job_b])
    db_session.flush()

    demo_files = []
    root = Path(demo_repo_path)
    for path in root.rglob("*"):
        if path.is_file():
            demo_files.append(
                FilePayload(relative_path=str(path.relative_to(root)), data=path.read_bytes())
            )

    stats_a = await index_files(db_session, source=source_a, job=job_a, files=demo_files + [secret_a])
    assert stats_a["indexed_chunks"] >= 1
    db_session.refresh(source_a)
    db_session.refresh(source_b)
    assert source_b.project_id == project_b.id, "source B project scope must remain after indexing source A"
    loaded_b = db_session.get(Source, source_b.id)
    assert loaded_b is not None and loaded_b.project_id == project_b.id
    stats_b = await index_files(db_session, source=loaded_b, job=job_b, files=[secret_b])
    assert stats_b["indexed_chunks"] >= 1, stats_b
    db_session.flush()
    db_session.expire_all()

    items_b = db_session.query(EvidenceItem).filter(EvidenceItem.source_id == source_b.id).all()
    assert items_b, "expected evidence rows for project B source"
    assert all(item.project_id == project_b.id for item in items_b), [
        (str(item.project_id), str(project_b.id)) for item in items_b
    ]

    hits_b = await RetrievalService(db_session).retrieve(
        organization_id=org.id,
        query="HSM partition API platform",
        project_id=project_b.id,
        limit=10,
    )
    assert hits_b
    assert all(item.project_id == project_b.id for item in hits_b)
    assert not any("SaaS platform customer data encryption" in item.content for item in hits_b)

    hits_a = await RetrievalService(db_session).retrieve(
        organization_id=org.id,
        query="customer data encryption at rest",
        project_id=project_a.id,
        limit=10,
    )
    assert hits_a
    assert all(item.project_id in (project_a.id, None) for item in hits_a)
    assert not any(item.project_id == project_b.id for item in hits_a)
    assert any("encrypt" in item.content.lower() for item in hits_a)


def test_api_evidence_requires_same_org(client: TestClient, db_session):
    org1 = Organization(name="Org1", slug="org1")
    org2 = Organization(name="Org2", slug="org2")
    user1 = User(email="a@example.com", full_name="A", hashed_password=hash_password("password"))
    db_session.add_all([org1, org2, user1])
    db_session.flush()
    db_session.add(
        OrganizationMembership(organization_id=org1.id, user_id=user1.id, role=Role.ORG_ADMIN.value)
    )
    source = Source(
        organization_id=org2.id,
        name="Other",
        source_type=SourceType.FILE_UPLOAD.value,
        scope=EvidenceScope.ORGANIZATION.value,
    )
    db_session.add(source)
    db_session.flush()
    db_session.add(
        EvidenceItem(
            organization_id=org2.id,
            source_id=source.id,
            source_type=source.source_type,
            scope=source.scope,
            file_name="secret.txt",
            file_path="secret.txt",
            content="Org2 secret",
            content_hash="abc",
        )
    )
    db_session.commit()

    token = create_access_token(str(user1.id), {"organization_id": str(org1.id), "role": Role.ORG_ADMIN.value})
    resp = client.get("/api/v1/evidence", headers=_auth_headers(token, str(org1.id)))
    assert resp.status_code == 200
    assert all(item["content"] != "Org2 secret" for item in resp.json())

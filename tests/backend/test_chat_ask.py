import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.roles import Role
from app.core.jwt_audiences import AUD_EMPLOYEE, AUD_ORG_ADMIN, AUD_PLATFORM
from app.core.security import create_access_token, hash_password
from app.models.enums import EvidenceScope, SourceType, SyncJobStatus
from app.models.organization import Organization, OrganizationMembership, User
from app.models.project import Project
from app.models.source import Source, SourceSyncJob
from app.services.ingestion.indexer import FilePayload, index_files


def _auth_headers(token: str, org_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}


@pytest.mark.asyncio
async def test_chat_ask_returns_evidence_backed_answer(client: TestClient, db_session, demo_repo_path: str):
    org = Organization(name="Acme Chat", slug="acme-chat")
    db_session.add(org)
    db_session.flush()
    user = User(email="chat@acme.example", hashed_password=hash_password("password"), full_name="Chat User")
    db_session.add(user)
    db_session.flush()
    db_session.add(
        OrganizationMembership(organization_id=org.id, user_id=user.id, role=Role.EDITOR.value),
    )
    project = Project(organization_id=org.id, name="Platform")
    db_session.add(project)
    db_session.flush()
    source = Source(
        organization_id=org.id,
        project_id=project.id,
        name="Demo",
        source_type=SourceType.FOLDER_ARCHIVE.value,
        scope=EvidenceScope.PROJECT.value,
    )
    db_session.add(source)
    db_session.flush()
    job = SourceSyncJob(organization_id=org.id, source_id=source.id, status=SyncJobStatus.RUNNING.value)
    db_session.add(job)
    db_session.flush()

    root = Path(demo_repo_path)
    files = [
        FilePayload(relative_path=str(p.relative_to(root)), data=p.read_bytes())
        for p in root.rglob("*")
        if p.is_file()
    ]
    await index_files(db_session, source=source, job=job, files=files)
    db_session.flush()

    token = create_access_token(str(user.id), {"organization_id": str(org.id), "role": Role.EDITOR.value})
    res = client.post(
        "/api/v1/chat/ask",
        headers=_auth_headers(token, str(org.id)),
        json={"query": "Do you encrypt customer data at rest?", "project_id": str(project.id)},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["query"]
    assert body["answer"]
    assert body["evidence_sufficiency"] in {"sufficient", "insufficient"}
    if body["evidence_sufficiency"] == "sufficient":
        assert len(body["citations"]) >= 1


def test_chat_ask_requires_auth(client: TestClient):
    res = client.post("/api/v1/chat/ask", json={"query": "hello"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_chat_greeting_is_conversational(client: TestClient, db_session):
    org = Organization(name="Greet Org", slug="greet-org", license_limit=5)
    db_session.add(org)
    db_session.flush()
    user = User(email="greet@acme.example", hashed_password=hash_password("password"), full_name="G")
    db_session.add(user)
    db_session.flush()
    db_session.add(
        OrganizationMembership(organization_id=org.id, user_id=user.id, role=Role.EDITOR.value),
    )
    project = Project(organization_id=org.id, name="P")
    db_session.add(project)
    db_session.flush()

    token = create_access_token(str(user.id), {"organization_id": str(org.id), "role": Role.EDITOR.value})
    res = client.post(
        "/api/v1/chat/ask",
        headers=_auth_headers(token, str(org.id)),
        json={"query": "hi", "project_id": str(project.id)},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body.get("conversational") is True
    assert body.get("outcome") == "conversational"
    assert body.get("citations") == []
    assert body.get("evidence_sufficiency") == "not_applicable"

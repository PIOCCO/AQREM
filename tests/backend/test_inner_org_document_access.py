"""
SMB document-level access control is NOT implemented today.

This test documents current behavior: any active org member (VIEWER or EDITOR)
can list and retrieve the same evidence within the organization/project scope.
When per-document ACL lands, replace these expectations with denial tests.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.roles import Role
from app.core.security import create_access_token, hash_password
from app.models.enums import EvidenceScope, SourceType, SyncJobStatus
from app.models.organization import Organization, OrganizationMembership, User
from app.models.project import Project
from app.models.source import Source, SourceSyncJob
from app.services.ingestion.indexer import FilePayload, index_files


def _headers(token: str, org_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}


@pytest.mark.asyncio
async def test_viewer_and_editor_see_same_sensitive_evidence(db_session, client: TestClient):
    org = Organization(name="SMB Co", slug="smb-co")
    db_session.add(org)
    db_session.flush()

    viewer = User(email="viewer@smb.example", hashed_password=hash_password("test"), full_name="Viewer")
    editor = User(email="editor@smb.example", hashed_password=hash_password("test"), full_name="Editor")
    db_session.add_all([viewer, editor])
    db_session.flush()
    db_session.add(
        OrganizationMembership(organization_id=org.id, user_id=viewer.id, role=Role.VIEWER.value),
    )
    db_session.add(
        OrganizationMembership(organization_id=org.id, user_id=editor.id, role=Role.EDITOR.value),
    )

    project = Project(organization_id=org.id, name="HR")
    db_session.add(project)
    db_session.flush()

    source = Source(
        organization_id=org.id,
        project_id=project.id,
        name="HR uploads",
        source_type=SourceType.FOLDER_ARCHIVE.value,
        scope=EvidenceScope.PROJECT.value,
    )
    db_session.add(source)
    db_session.flush()
    job = SourceSyncJob(organization_id=org.id, source_id=source.id, status=SyncJobStatus.RUNNING.value)
    db_session.add(job)
    db_session.flush()

    await index_files(
        db_session,
        source=source,
        job=job,
        files=[
            FilePayload(
                relative_path="hr/salary_confidential.txt",
                data=b"Karim salary 120000 MAD - HR confidential",
            ),
        ],
    )
    db_session.flush()

    def token(user: User, role: Role) -> str:
        return create_access_token(
            str(user.id),
            {
                "organization_id": str(org.id),
                "role": role.value,
                "aud": "aqrem-employee",
            },
        )

    hv = _headers(token(viewer, Role.VIEWER), str(org.id))
    he = _headers(token(editor, Role.EDITOR), str(org.id))

    rv = client.get("/api/v1/evidence", headers=hv)
    re = client.get("/api/v1/evidence", headers=he)
    assert rv.status_code == 200 and re.status_code == 200
    assert rv.json()["total"] == re.json()["total"] >= 1
    names = {i["file_name"] for i in rv.json()["items"]}
    assert "salary_confidential.txt" in names

    chat = client.post(
        "/api/v1/chat/ask",
        headers=hv,
        json={"query": "What is Karim's salary?", "project_id": str(project.id)},
    )
    assert chat.status_code == 200
    body = chat.json()
    # Today retrieval is not filtered by document ACL; mock LLM may still refuse or cite.
    assert body.get("outcome") != "access_denied"

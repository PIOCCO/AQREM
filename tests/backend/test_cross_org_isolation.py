"""Two-organization isolation proof (shared tier).

Org A and org B each index a document containing a unique secret marker. Every
data-plane path (retrieval preview, chat ask, evidence list/get, org-admin document
list/delete, members, audit, chat shares) is exercised as org A and must never
return org B content, and header spoofing of X-Organization-Id must be refused.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.jwt_audiences import AUD_ORG_ADMIN
from app.core.roles import Role
from app.core.security import create_access_token, hash_password
from app.models.client_admin import ClientDocument
from app.models.enums import EvidenceScope, SourceType, SyncJobStatus
from app.models.evidence import EvidenceItem
from app.models.organization import Organization, OrganizationMembership, User
from app.models.project import Project
from app.models.source import Source, SourceSyncJob
from app.services.ingestion.indexer import FilePayload, index_files
from app.services.retrieval.service import RetrievalService
from app.services.storage.path_utils import assert_blob_in_org, org_blob_path
from tests.backend.helpers_acl import mark_source_visible_to_all_staff

SECRET_A = "ALPHAMARKER7731 orchids encryption key rotation every 30 days"
SECRET_B = "BRAVOMARKER9920 orchids encryption key rotation every 90 days"


def _h(token: str, org_id) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Organization-Id": str(org_id)}


async def _seed_org(db, name: str, secret: str):
    org = Organization(name=name, slug=f"{name.lower()}-{uuid4().hex[:6]}", license_limit=10)
    db.add(org)
    db.flush()
    admin = User(email=f"admin-{uuid4().hex[:6]}@{name.lower()}.test", full_name=f"{name} Admin",
                 hashed_password=hash_password("x"), is_active=True)
    emp = User(email=f"emp-{uuid4().hex[:6]}@{name.lower()}.test", full_name=f"{name} Emp",
               hashed_password=hash_password("x"), is_active=True)
    db.add_all([admin, emp])
    db.flush()
    db.add_all([
        OrganizationMembership(organization_id=org.id, user_id=admin.id, role=Role.ORG_ADMIN.value),
        OrganizationMembership(organization_id=org.id, user_id=emp.id, role=Role.EDITOR.value),
    ])
    project = Project(organization_id=org.id, name=f"{name} Project")
    db.add(project)
    db.flush()
    source = Source(organization_id=org.id, project_id=project.id, name=f"{name} docs",
                    source_type=SourceType.FILE_UPLOAD.value, scope=EvidenceScope.ORGANIZATION.value)
    mark_source_visible_to_all_staff(source)
    db.add(source)
    db.flush()
    job = SourceSyncJob(organization_id=org.id, source_id=source.id, status=SyncJobStatus.RUNNING.value)
    db.add(job)
    db.flush()
    await index_files(db, source=source, job=job,
                      files=[FilePayload(relative_path="policy.txt", data=secret.encode())])
    doc = ClientDocument(organization_id=org.id, source_id=source.id, file_name=f"{name}-policy.txt",
                         blob_path=org_blob_path(org.id, str(source.id), "policy.txt"),
                         status="indexed", visibility_mode="all_staff")
    db.add(doc)
    db.commit()
    admin_tok = create_access_token(str(admin.id), {"organization_id": str(org.id), "role": Role.ORG_ADMIN.value},
                                    audience=AUD_ORG_ADMIN)
    emp_tok = create_access_token(str(emp.id), {"organization_id": str(org.id), "role": Role.EDITOR.value})
    return {"org": org, "admin_tok": admin_tok, "emp_tok": emp_tok, "doc": doc, "project": project,
            "source": source}


@pytest.fixture()
def two_orgs(db_session):
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        a = loop.run_until_complete(_seed_org(db_session, "Alpha", SECRET_A))
        b = loop.run_until_complete(_seed_org(db_session, "Bravo", SECRET_B))
    finally:
        loop.close()
    return a, b


@pytest.mark.asyncio
async def test_retrieval_service_never_returns_other_org_chunks(db_session, two_orgs):
    a, b = two_orgs
    for org_ctx, other in ((a, b), (b, a)):
        hits = await RetrievalService(db_session).retrieve(
            organization_id=org_ctx["org"].id, query="orchids encryption key rotation", limit=12
        )
        assert hits, "own org content should be retrievable"
        assert all(h.organization_id == org_ctx["org"].id for h in hits)
        other_marker = SECRET_B[:15] if other is b else SECRET_A[:15]
        assert not any(other_marker in (h.content or "") for h in hits)
        # Passing the other org's project/source ids must not widen scope.
        hits2 = await RetrievalService(db_session).retrieve(
            organization_id=org_ctx["org"].id, query="orchids", project_id=other["project"].id,
            source_id=other["source"].id, limit=12,
        )
        assert all(h.organization_id == org_ctx["org"].id for h in hits2)


def test_retrieval_preview_and_chat_api_isolated(client: TestClient, two_orgs):
    a, b = two_orgs
    r = client.post("/api/v1/retrieval/preview", headers=_h(a["emp_tok"], a["org"].id),
                    json={"query": "orchids encryption key rotation", "limit": 12})
    assert r.status_code == 200, r.text
    assert "ALPHAMARKER7731" in r.text
    assert "BRAVOMARKER9920" not in r.text

    r = client.post("/api/v1/chat/ask", headers=_h(a["emp_tok"], a["org"].id),
                    json={"query": "How often is the orchids encryption key rotated?",
                          "project_id": str(b["project"].id)})
    assert r.status_code in (200, 400), r.text
    assert "BRAVOMARKER9920" not in r.text
    assert "90 days" not in r.text
    assert "Bravo Project" not in r.text  # project name of another org must not leak

    r = client.post("/api/v1/chat/ask/stream", headers=_h(a["emp_tok"], a["org"].id),
                    json={"query": "orchids encryption key rotation"})
    assert r.status_code == 200
    assert "BRAVOMARKER9920" not in r.text


def test_header_spoofing_other_org_is_refused(client: TestClient, two_orgs):
    a, b = two_orgs
    for path, method, body in (
        ("/api/v1/retrieval/preview", "post", {"query": "orchids"}),
        ("/api/v1/chat/ask", "post", {"query": "orchids"}),
        ("/api/v1/evidence", "get", None),
        ("/api/v1/org-admin/documents", "get", None),
    ):
        tok = a["admin_tok"] if "org-admin" in path else a["emp_tok"]
        r = client.request(method.upper(), path, headers=_h(tok, b["org"].id), json=body)
        assert r.status_code in (401, 403, 404), (path, r.status_code, r.text)
        assert "BRAVOMARKER9920" not in r.text


def test_evidence_list_and_get_isolated(client: TestClient, db_session, two_orgs):
    a, b = two_orgs
    r = client.get("/api/v1/evidence", headers=_h(a["emp_tok"], a["org"].id))
    assert r.status_code == 200
    assert "BRAVOMARKER9920" not in r.text
    b_item = db_session.query(EvidenceItem).filter(EvidenceItem.organization_id == b["org"].id).first()
    assert b_item is not None
    r = client.get(f"/api/v1/evidence/{b_item.id}", headers=_h(a["admin_tok"], a["org"].id))
    assert r.status_code == 404
    assert "BRAVOMARKER9920" not in r.text


def test_org_admin_document_list_and_delete_isolated(client: TestClient, db_session, two_orgs):
    a, b = two_orgs
    r = client.get("/api/v1/org-admin/documents", headers=_h(a["admin_tok"], a["org"].id))
    assert r.status_code == 200, r.text
    assert "Alpha-policy.txt" in r.text
    assert "Bravo-policy.txt" not in r.text
    r = client.delete(f"/api/v1/org-admin/documents/{b['doc'].id}", headers=_h(a["admin_tok"], a["org"].id))
    assert r.status_code == 404
    db_session.expire_all()
    assert db_session.get(ClientDocument, b["doc"].id) is not None
    r = client.post(f"/api/v1/org-admin/documents/{b['doc'].id}/retry", headers=_h(a["admin_tok"], a["org"].id))
    assert r.status_code == 404


def test_org_admin_members_and_audit_isolated(client: TestClient, two_orgs):
    a, b = two_orgs
    r = client.get("/api/v1/org-admin/members", headers=_h(a["admin_tok"], a["org"].id))
    assert r.status_code == 200, r.text
    assert "@bravo.test" not in r.text
    r = client.get("/api/v1/org-admin/audit", headers=_h(a["admin_tok"], a["org"].id))
    assert r.status_code == 200, r.text
    assert str(b["org"].id) not in r.text


def test_chat_share_of_other_org_not_readable(client: TestClient, db_session, two_orgs):
    a, b = two_orgs
    from app.models.chat_share import ChatConversationShare
    from datetime import UTC, datetime, timedelta

    share = ChatConversationShare(organization_id=b["org"].id, client_conversation_id="conv-b",
                                  share_token=f"tok{uuid4().hex}", title="B chat",
                                  messages=[{"role": "user", "content": "BRAVOMARKER9920"}],
                                  expires_at=datetime.now(UTC) + timedelta(days=1))
    for col in ChatConversationShare.__table__.columns:
        if col.name == "created_by_user_id" and not col.nullable:
            share.created_by_user_id = db_session.query(OrganizationMembership).filter_by(
                organization_id=b["org"].id).first().user_id
    db_session.add(share)
    db_session.commit()
    r = client.get(f"/api/v1/chat/shares/{share.share_token}", headers=_h(a["admin_tok"], a["org"].id))
    assert r.status_code in (403, 404)
    assert "BRAVOMARKER9920" not in r.text
    r = client.delete(f"/api/v1/chat/shares/{share.share_token}", headers=_h(a["admin_tok"], a["org"].id))
    assert r.status_code in (403, 404)


def test_blob_paths_are_org_prefixed_and_guarded(two_orgs):
    a, b = two_orgs
    assert a["doc"].blob_path.startswith(f"{a['org'].id}/")
    assert_blob_in_org(a["doc"].blob_path, a["org"].id)
    with pytest.raises(ValueError):
        assert_blob_in_org(b["doc"].blob_path, a["org"].id)
    with pytest.raises(ValueError):
        assert_blob_in_org(f"{a['org'].id}/../{b['org'].id}/x", a["org"].id)
    with pytest.raises(ValueError):
        org_blob_path(a["org"].id, "..", "x")

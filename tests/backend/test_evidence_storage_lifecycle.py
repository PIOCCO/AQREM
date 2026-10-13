"""Evidence and blob storage isolation (API + path safety)."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.jwt_audiences import AUD_EMPLOYEE, AUD_ORG_ADMIN
from app.core.roles import Role
from app.core.security import create_access_token, hash_password
from app.models.enums import EvidenceScope, SourceType
from app.models.evidence import EvidenceItem
from app.models.organization import Organization, OrganizationMembership, User
from app.models.project import Project
from app.models.source import Source
from app.services.storage.local import LocalBlobStorage
from app.services.storage.path_utils import resolve_under_root, safe_blob_filename
import pytest
from pathlib import Path


def _headers(token: str, org_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}


def _seed_tenant(db, slug: str, role: str = Role.EDITOR.value) -> tuple[Organization, User, str, Project, Source]:
    org = Organization(name=slug, slug=slug, license_limit=10, is_active=True)
    db.add(org)
    db.flush()
    project = Project(organization_id=org.id, name="P")
    db.add(project)
    db.flush()
    user = User(email=f"{slug}@ev.test", full_name=slug, hashed_password=hash_password("password"))
    db.add(user)
    db.flush()
    db.add(
        OrganizationMembership(organization_id=org.id, user_id=user.id, role=role, is_active=True)
    )
    source = Source(
        organization_id=org.id,
        project_id=project.id,
        name="S",
        source_type=SourceType.FOLDER_ARCHIVE.value,
        scope=EvidenceScope.PROJECT.value,
    )
    db.add(source)
    db.flush()
    evidence = EvidenceItem(
        organization_id=org.id,
        project_id=project.id,
        source_id=source.id,
        source_type=source.source_type,
        scope=source.scope,
        file_name="lifecycle.md",
        file_path="lifecycle.md",
        content="org-private-content",
        content_hash="abc123",
    )
    db.add(evidence)
    db.commit()
    aud = AUD_ORG_ADMIN if role == Role.ORG_ADMIN.value else AUD_EMPLOYEE
    token = create_access_token(
        str(user.id),
        {"organization_id": str(org.id), "role": role, "auth_version": 1},
        audience=aud,
    )
    return org, user, token, project, source


def test_evidence_get_requires_same_org(client: TestClient, db_session):
    org_a, _, tok_a, _, _ = _seed_tenant(db_session, "life-a")
    org_b, _, _, _, _ = _seed_tenant(db_session, "life-b")
    ev_b = db_session.query(EvidenceItem).filter(EvidenceItem.organization_id == org_b.id).one()
    res = client.get(f"/api/v1/evidence/{ev_b.id}", headers=_headers(tok_a, str(org_a.id)))
    assert res.status_code == 404


def test_retrieval_preview_excludes_other_org_content(client: TestClient, db_session):
    org_a, _, tok_a, project_a, _ = _seed_tenant(db_session, "ret-a")
    org_b, _, _, project_b, _ = _seed_tenant(db_session, "ret-b")
    ev_b = db_session.query(EvidenceItem).filter(EvidenceItem.organization_id == org_b.id).one()
    res = client.post(
        "/api/v1/retrieval/preview",
        headers=_headers(tok_a, str(org_a.id)),
        json={"query": "org-private-content", "project_id": str(project_a.id)},
    )
    assert res.status_code == 200
    ids = {item["id"] for item in res.json().get("items", [])}
    assert str(ev_b.id) not in ids
    # Cross-project id in payload must not pull tenant B rows
    res2 = client.post(
        "/api/v1/retrieval/preview",
        headers=_headers(tok_a, str(org_a.id)),
        json={"query": "org-private-content", "project_id": str(project_b.id)},
    )
    assert res2.status_code in (200, 403, 404)
    if res2.status_code == 200:
        ids2 = {item["id"] for item in res2.json().get("items", [])}
        assert str(ev_b.id) not in ids2


def test_upload_filename_sanitizer_rejects_path_traversal():
    with pytest.raises(ValueError, match="Invalid upload filename"):
        safe_blob_filename("../../etc/passwd")
    with pytest.raises(ValueError, match="Invalid upload filename"):
        safe_blob_filename("foo/../../../secret.txt")


def test_blob_storage_cannot_escape_root(tmp_path: Path):
    root = tmp_path / "blobs"
    storage = LocalBlobStorage(str(root))
    storage.upload_bytes("org1/src/file.txt", b"ok", "text/plain")
    with pytest.raises(ValueError, match="Invalid blob path"):
        resolve_under_root(root, "../outside")
    with pytest.raises(ValueError, match="Invalid blob path"):
        storage.download_bytes("../../etc/passwd")

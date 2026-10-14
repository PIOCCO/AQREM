"""Chat composer attachment uploads."""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from app.core.roles import Role
from app.core.security import create_access_token, hash_password
from app.models.organization import Organization, OrganizationMembership, User


def _headers(token: str, org_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}


def _seed_editor(db_session) -> tuple[Organization, str]:
    org = Organization(name="Chat Attach Co", slug="chat-attach-co", license_limit=10)
    db_session.add(org)
    db_session.flush()
    user = User(email="editor@chat.test", full_name="Ed", hashed_password=hash_password("password"))
    db_session.add(user)
    db_session.flush()
    db_session.add(
        OrganizationMembership(organization_id=org.id, user_id=user.id, role=Role.EDITOR.value),
    )
    db_session.commit()
    token = create_access_token(
        str(user.id),
        {"organization_id": str(org.id), "role": Role.EDITOR.value, "aud": "aqrem-employee"},
    )
    return org, token


def _seed_viewer(db_session, org: Organization) -> str:
    user = User(email="viewer@chat.test", full_name="Vi", hashed_password=hash_password("password"))
    db_session.add(user)
    db_session.flush()
    db_session.add(
        OrganizationMembership(organization_id=org.id, user_id=user.id, role=Role.VIEWER.value),
    )
    db_session.commit()
    return create_access_token(
        str(user.id),
        {"organization_id": str(org.id), "role": Role.VIEWER.value, "aud": "aqrem-employee"},
    )


def test_limits_endpoint(client: TestClient):
    res = client.get("/api/v1/chat/attachment-limits")
    assert res.status_code == 200
    body = res.json()
    assert body["max_files_per_message"] == 3
    assert ".pdf" in body["allowed_extensions"]


def test_viewer_forbidden(client: TestClient, db_session):
    org, _ed = _seed_editor(db_session)
    viewer_token = _seed_viewer(db_session, org)
    res = client.post(
        "/api/v1/chat/attachments",
        headers=_headers(viewer_token, str(org.id)),
        files={"file": ("note.txt", b"hello", "text/plain")},
    )
    assert res.status_code == 403


def test_rejects_tar_gz(client: TestClient, db_session):
    org, token = _seed_editor(db_session)
    res = client.post(
        "/api/v1/chat/attachments",
        headers=_headers(token, str(org.id)),
        files={"file": ("bundle.tar.gz", b"fake", "application/gzip")},
    )
    assert res.status_code == 415
    assert "Documents" in res.json()["detail"]["message"]


def test_rejects_oversize(client: TestClient, db_session, monkeypatch):
    monkeypatch.setenv("CHAT_ATTACHMENT_MAX_MB", "1")
    from app.core.config import get_settings

    get_settings.cache_clear()
    org, token = _seed_editor(db_session)
    big = b"x" * (2 * 1024 * 1024)
    res = client.post(
        "/api/v1/chat/attachments",
        headers=_headers(token, str(org.id)),
        files={"file": ("big.txt", big, "text/plain")},
    )
    get_settings.cache_clear()
    assert res.status_code == 413


def test_rejects_fake_pdf(client: TestClient, db_session):
    org, token = _seed_editor(db_session)
    res = client.post(
        "/api/v1/chat/attachments",
        headers=_headers(token, str(org.id)),
        files={"file": ("evil.pdf", b"not a pdf", "application/pdf")},
    )
    assert res.status_code == 415


def test_accepts_small_txt(client: TestClient, db_session, monkeypatch, tmp_path):
    monkeypatch.setenv("LOCAL_UPLOAD_DIR", str(tmp_path / "uploads"))
    from app.core.config import get_settings

    get_settings.cache_clear()
    org, token = _seed_editor(db_session)
    res = client.post(
        "/api/v1/chat/attachments",
        headers=_headers(token, str(org.id)),
        files={"file": ("note.txt", b"Policy excerpt for chat.", "text/plain")},
    )
    get_settings.cache_clear()
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["file_name"] == "note.txt"
    assert body["id"]


def test_pdf_page_limit(client: TestClient, db_session, monkeypatch):
    monkeypatch.setenv("CHAT_ATTACHMENT_MAX_PDF_PAGES", "2")
    from app.core.config import get_settings

    get_settings.cache_clear()
    org, token = _seed_editor(db_session)
    buf = io.BytesIO()
    w = PdfWriter()
    for _ in range(5):
        w.add_blank_page(width=200, height=200)
    w.write(buf)
    res = client.post(
        "/api/v1/chat/attachments",
        headers=_headers(token, str(org.id)),
        files={"file": ("long.pdf", buf.getvalue(), "application/pdf")},
    )
    get_settings.cache_clear()
    assert res.status_code == 422
    assert "5 pages" in res.json()["detail"]["message"]

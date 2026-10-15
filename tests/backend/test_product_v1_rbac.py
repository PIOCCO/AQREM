"""Product V1: org-wide documents, admin API isolation, chat share restrictions."""

from __future__ import annotations

import io
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.core.jwt_audiences import AUD_EMPLOYEE, AUD_ORG_ADMIN
from app.core.roles import Role
from app.core.security import create_access_token, hash_password
from app.models.organization import Organization, OrganizationMembership, User
from app.models.tenant_data_store import TenantDataStoreConfig
from app.tenant_store.resolver import MANAGED_COLOCATED


def _headers(token: str, org_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}


def _seed_viewer(db_session) -> tuple[Organization, str]:
    org = Organization(name="V1 RBAC", slug="v1-rbac", license_limit=5, chat_shares_enabled=True)
    db_session.add(org)
    db_session.flush()
    user = User(email="viewer@v1.com", hashed_password=hash_password("x"), full_name="Viewer", is_active=True)
    db_session.add(user)
    db_session.flush()
    db_session.add(
        OrganizationMembership(organization_id=org.id, user_id=user.id, role=Role.VIEWER.value, is_active=True)
    )
    db_session.commit()
    token = create_access_token(
        str(user.id),
        {"organization_id": str(org.id), "role": Role.VIEWER.value, "auth_version": 1},
        audience=AUD_EMPLOYEE,
    )
    return org, token


@pytest.fixture(autouse=True)
def product_v1_enabled(monkeypatch):
    monkeypatch.setenv("PRODUCT_V1", "true")
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_employee_cannot_access_org_admin_overview(client: TestClient, db_session):
    org, token = _seed_viewer(db_session)
    res = client.get("/api/v1/org-admin/overview", headers=_headers(token, str(org.id)))
    assert res.status_code == 403


def test_chat_shares_blocked_in_product_v1(client: TestClient, db_session):
    org, token = _seed_viewer(db_session)
    payload = {
        "client_conversation_id": "local-1",
        "title": "Test",
        "messages": [{"role": "user", "content": "Hi", "created_at": "2026-01-01T00:00:00Z"}],
    }
    res = client.post("/api/v1/chat/shares", headers=_headers(token, str(org.id)), json=payload)
    assert res.status_code == 403


def test_upload_forces_all_staff_visibility(client: TestClient, db_session, monkeypatch, tmp_path):
    monkeypatch.setenv("LOCAL_UPLOAD_DIR", str(tmp_path / "up"))
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr("app.core.broker_health.assert_broker_available", lambda: None)
    monkeypatch.setattr("app.services.ingestion.enqueue.enqueue_source_sync_for_job", lambda *a, **k: None)
    org = Organization(name="Up", slug="v1-up", license_limit=5)
    db_session.add(org)
    db_session.flush()
    admin = User(email="admin@v1.com", hashed_password=hash_password("x"), full_name="Admin", is_active=True)
    db_session.add(admin)
    db_session.flush()
    db_session.add(OrganizationMembership(organization_id=org.id, user_id=admin.id, role=Role.ORG_ADMIN.value))
    db_session.add(
        TenantDataStoreConfig(
            organization_id=org.id,
            storage_mode=MANAGED_COLOCATED,
            connection_method="managed",
            status="active",
            setup_validated_at=datetime.now(UTC),
        )
    )
    db_session.commit()
    token = create_access_token(
        str(admin.id),
        {"organization_id": str(org.id), "role": Role.ORG_ADMIN.value, "aud": "aqrem-org-admin"},
        audience=AUD_ORG_ADMIN,
    )
    res = client.post(
        "/api/v1/org-admin/documents/upload",
        headers=_headers(token, str(org.id)),
        files=[("files", ("note.txt", io.BytesIO(b"hello"), "text/plain"))],
        data={"visibility_mode": "admins_only"},
    )
    assert res.status_code == 200, res.text
    listing = client.get("/api/v1/org-admin/documents", headers=_headers(token, str(org.id)))
    assert listing.json()["items"][0]["visibility_mode"] == "all_staff"

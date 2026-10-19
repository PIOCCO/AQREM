"""Document upload: storage, database gate, happy path."""

from __future__ import annotations

import io
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.jwt_audiences import AUD_ORG_ADMIN
from app.core.roles import Role
from app.core.security import create_access_token, hash_password
from app.models.organization import Organization, OrganizationMembership, User
from app.models.tenant_data_store import TenantDataStoreConfig
from app.tenant_store.resolver import MANAGED_COLOCATED


def _headers(token: str, org_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}


def _seed_admin(db_session, *, postgres_validated: bool = True) -> tuple[Organization, str]:
    org = Organization(name="Doc Up", slug=f"du-{uuid4().hex[:8]}", license_limit=5)
    db_session.add(org)
    db_session.flush()
    admin = User(email=f"a-{uuid4().hex[:6]}@t.com", full_name="Admin", hashed_password=hash_password("x"), is_active=True)
    db_session.add(admin)
    db_session.flush()
    db_session.add(OrganizationMembership(organization_id=org.id, user_id=admin.id, role=Role.ORG_ADMIN.value))
    if postgres_validated:
        from datetime import UTC, datetime

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
    return org, token


def test_upload_blocked_when_postgres_not_validated(client: TestClient, db_session, monkeypatch, tmp_path):
    monkeypatch.setenv("LOCAL_UPLOAD_DIR", str(tmp_path / "up"))
    from app.core.config import get_settings

    get_settings.cache_clear()
    org, token = _seed_admin(db_session, postgres_validated=False)
    res = client.post(
        "/api/v1/org-admin/documents/upload",
        headers=_headers(token, str(org.id)),
        files=[("files", ("a.txt", io.BytesIO(b"hi"), "text/plain"))],
        data={"visibility_mode": "admins_only"},
    )
    assert res.status_code == 503
    assert res.json()["detail"]["code"] == "DATABASE_NOT_CONFIGURED"


def test_upload_blocked_when_storage_not_writable(client: TestClient, db_session, monkeypatch, tmp_path):
    # A file used as the upload directory fails deterministically on every OS.
    blocked = tmp_path / "not-a-directory"
    blocked.write_text("occupied")
    monkeypatch.setenv("LOCAL_UPLOAD_DIR", str(blocked))
    from app.core.config import get_settings

    get_settings.cache_clear()
    org, token = _seed_admin(db_session)
    res = client.post(
        "/api/v1/org-admin/documents/upload",
        headers=_headers(token, str(org.id)),
        files=[("files", ("a.txt", io.BytesIO(b"hi"), "text/plain"))],
        data={"visibility_mode": "admins_only"},
    )
    assert res.status_code == 503
    assert res.json()["detail"]["code"] == "STORAGE_UNAVAILABLE"


def test_upload_txt_creates_document(client: TestClient, db_session, monkeypatch, tmp_path):
    monkeypatch.setenv("LOCAL_UPLOAD_DIR", str(tmp_path / "up"))
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr("app.core.broker_health.assert_broker_available", lambda: None)
    monkeypatch.setattr("app.services.ingestion.enqueue.enqueue_source_sync_for_job", lambda *a, **k: None)
    org, token = _seed_admin(db_session)
    res = client.post(
        "/api/v1/org-admin/documents/upload",
        headers=_headers(token, str(org.id)),
        files=[("files", ("note.txt", io.BytesIO(b"hello"), "text/plain"))],
        data={"visibility_mode": "admins_only"},
    )
    assert res.status_code == 200, res.text
    listing = client.get("/api/v1/org-admin/documents", headers=_headers(token, str(org.id)))
    assert listing.status_code == 200
    body = listing.json()
    assert body["counts"]["total"] == 1
    assert body["items"][0]["status"] in ("queued", "indexing")


def test_upload_rolls_back_when_enqueue_fails(client: TestClient, db_session, monkeypatch, tmp_path):
    monkeypatch.setenv("LOCAL_UPLOAD_DIR", str(tmp_path / "up"))
    from app.core.config import get_settings

    get_settings.cache_clear()
    org, token = _seed_admin(db_session)

    def _fail_enqueue(*_args, **_kwargs):
        from app.services.ingestion.enqueue import IngestionEnqueueError

        raise IngestionEnqueueError("BROKER_UNAVAILABLE", "Could not queue indexing job (worker or broker unavailable).")

    monkeypatch.setattr("app.services.ingestion.enqueue.enqueue_source_sync_for_job", _fail_enqueue)

    res = client.post(
        "/api/v1/org-admin/documents/upload",
        headers=_headers(token, str(org.id)),
        files=[("files", ("note.txt", io.BytesIO(b"hello"), "text/plain"))],
        data={"visibility_mode": "admins_only"},
    )
    assert res.status_code == 503
    assert res.json()["detail"]["code"] == "BROKER_UNAVAILABLE"
    listing = client.get("/api/v1/org-admin/documents", headers=_headers(token, str(org.id)))
    assert listing.status_code == 200
    assert listing.json()["counts"]["total"] == 0

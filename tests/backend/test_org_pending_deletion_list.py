"""Pending deletion filter and restore."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.jwt_audiences import AUD_PLATFORM
from app.core.platform_roles import PlatformRole
from app.core.security import create_access_token, hash_password
from app.models.organization import Organization, User


def _super(db_session) -> str:
    user = User(
        email="pending-list-super@test.local",
        full_name="Super",
        hashed_password=hash_password("password"),
        is_platform_admin=True,
        platform_role=PlatformRole.SUPER_ADMIN.value,
        platform_auth_version=1,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return create_access_token(
        str(user.id),
        {"aud": "aqrem-master", "platform_role": user.platform_role, "platform_auth_version": 1},
        audience=AUD_PLATFORM,
    )


def test_pending_deletion_filter_and_restore(client: TestClient, db_session):
    token = _super(db_session)
    org_id = client.post(
        "/api/v1/admin/organizations",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Pending Filter Org", "license_limit": 2, "environment": "production"},
    ).json()["id"]
    deleted = client.post(
        f"/api/v1/admin/organizations/{org_id}/delete",
        headers={"Authorization": f"Bearer {token}"},
        json={"confirmName": "Pending Filter Org"},
    )
    assert deleted.status_code == 200, deleted.text
    main = client.get("/api/v1/admin/organizations", headers={"Authorization": f"Bearer {token}"}).json()
    assert not any(o["id"] == org_id for o in main["items"])
    pending = client.get(
        "/api/v1/admin/organizations?status=pending_deletion",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    assert any(o["id"] == org_id for o in pending["items"])
    assert pending["items"][0]["deletion_status"] == "pending_deletion"
    restored = client.post(
        f"/api/v1/admin/organizations/{org_id}/restore",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert restored.status_code == 200, restored.text
    org = db_session.get(Organization, org_id)
    assert org is not None
    assert org.deleted_at is None

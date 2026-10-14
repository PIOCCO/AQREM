"""Org-admin invitation provisioning counts toward pending seats before accept."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.jwt_audiences import AUD_PLATFORM
from app.core.platform_roles import PlatformRole
from app.core.security import create_access_token, hash_password
from app.models.organization import OrganizationMembership, User


def _super(db_session) -> str:
    user = User(
        email="seat-super@test.local",
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


def test_admin_invite_pending_counts_before_accept(client: TestClient, db_session):
    token = _super(db_session)
    org_id = client.post(
        "/api/v1/admin/organizations",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Seat Pending Org", "license_limit": 5, "environment": "production"},
    ).json()["id"]
    created = client.post(
        f"/api/v1/admin/organizations/{org_id}/invitations/admin",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "pending-admin@corp.example", "full_name": "Pending Admin", "expires_days": 7},
    )
    assert created.status_code == 201, created.text
    listed = client.get("/api/v1/admin/organizations", headers={"Authorization": f"Bearer {token}"}).json()
    org = next(item for item in listed["items"] if item["id"] == org_id)
    assert org["seats"]["pending_invitations"] >= 1
    membership = (
        db_session.query(OrganizationMembership)
        .join(User, User.id == OrganizationMembership.user_id)
        .filter(User.email == "pending-admin@corp.example")
        .first()
    )
    assert membership is not None
    assert membership.is_active is False

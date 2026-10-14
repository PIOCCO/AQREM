"""Organization soft delete and authorization."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.jwt_audiences import AUD_PLATFORM
from app.core.platform_roles import PlatformRole
from app.core.security import create_access_token, hash_password
from app.models.organization import Organization, User


def _platform_token(user: User) -> str:
    return create_access_token(
        str(user.id),
        {"aud": "aqrem-master", "platform_role": user.platform_role, "platform_auth_version": 1},
        audience=AUD_PLATFORM,
    )


def _seed_super_admin(db_session) -> tuple[User, str]:
    user = User(
        email="del-super@test.local",
        full_name="Super",
        hashed_password=hash_password("password"),
        is_platform_admin=True,
        platform_role=PlatformRole.SUPER_ADMIN.value,
        platform_auth_version=1,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user, _platform_token(user)


def _seed_billing(db_session) -> tuple[User, str]:
    user = User(
        email="billing-del@test.local",
        full_name="Billing",
        hashed_password=hash_password("password"),
        platform_role=PlatformRole.PLATFORM_BILLING.value,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user, _platform_token(user)


def _create_org(client: TestClient, token: str, name: str = "Delete Me Org") -> str:
    res = client.post(
        "/api/v1/admin/organizations",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": name, "license_limit": 3, "environment": "production"},
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def test_delete_org_via_patch_confirm_name(client: TestClient, db_session):
    _user, token = _seed_super_admin(db_session)
    org_id = _create_org(client, token, name="Patch Delete Org")
    res = client.patch(
        f"/api/v1/admin/organizations/{org_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"confirmName": "Patch Delete Org"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["retention_days"] == 30


def test_delete_org_requires_exact_name(client: TestClient, db_session):
    _user, token = _seed_super_admin(db_session)
    org_id = _create_org(client, token, name="Exact Name Org")
    bad = client.request(
        "DELETE",
        f"/api/v1/admin/organizations/{org_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"confirmName": "exact name org"},
    )
    assert bad.status_code == 400
    good = client.post(
        f"/api/v1/admin/organizations/{org_id}/delete",
        headers={"Authorization": f"Bearer {token}"},
        json={"confirmName": "Exact Name Org"},
    )
    assert good.status_code == 200, good.text
    assert good.json()["retention_days"] == 30
    listed = client.get("/api/v1/admin/organizations", headers={"Authorization": f"Bearer {token}"}).json()
    assert not any(item["id"] == org_id for item in listed["items"])


def test_delete_org_forbidden_for_billing(client: TestClient, db_session):
    _super, super_token = _seed_super_admin(db_session)
    _billing, billing_token = _seed_billing(db_session)
    org_id = _create_org(client, super_token, name="Billing Block Org")
    res = client.request(
        "DELETE",
        f"/api/v1/admin/organizations/{org_id}",
        headers={"Authorization": f"Bearer {billing_token}"},
        json={"confirmName": "Billing Block Org"},
    )
    assert res.status_code == 403


def test_delete_org_revokes_invitations(client: TestClient, db_session):
    from app.models.invitation import UserInvitation

    _user, token = _seed_super_admin(db_session)
    org_id = _create_org(client, token, name="Invite Clean Org")
    inv = client.post(
        f"/api/v1/admin/organizations/{org_id}/invitations/admin",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "admin@del.example", "full_name": "Admin", "expires_days": 7},
    )
    assert inv.status_code == 201
    client.request(
        "DELETE",
        f"/api/v1/admin/organizations/{org_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"confirmName": "Invite Clean Org"},
    )
    row = (
        db_session.query(UserInvitation)
        .filter(UserInvitation.organization_id == org_id)
        .order_by(UserInvitation.created_at.desc())
        .first()
    )
    assert row is not None
    assert row.revoked_at is not None
    org = db_session.get(Organization, org_id)
    assert org is not None
    assert org.deleted_at is not None

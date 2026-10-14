"""Prove delete/remove mutations persist in the database and list endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient

from app.core.jwt_audiences import AUD_PLATFORM
from app.core.platform_roles import PlatformRole
from app.core.roles import Role
from app.core.security import create_access_token, hash_password
from app.models.invitation import UserInvitation
from app.models.organization import Organization, OrganizationMembership, User
from app.services.platform_provisioning import provision_user_invitation


def _platform_token(user: User) -> str:
    return create_access_token(
        str(user.id),
        {"aud": "aqrem-master", "platform_role": user.platform_role, "platform_auth_version": 1},
        audience=AUD_PLATFORM,
    )


def _seed_super(db_session) -> tuple[User, str]:
    user = User(
        email="persist-super@test.local",
        full_name="Super",
        hashed_password=hash_password("x"),
        is_platform_admin=True,
        platform_role=PlatformRole.SUPER_ADMIN.value,
        platform_auth_version=1,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user, _platform_token(user)


def test_org_delete_persists_deleted_at_and_list_excludes(client: TestClient, db_session):
    _super, token = _seed_super(db_session)
    org = Organization(name="Persist Delete Org", slug="persist-del", license_limit=3, license_status="active", is_active=True)
    db_session.add(org)
    db_session.commit()

    before = db_session.get(Organization, org.id)
    assert before is not None and before.deleted_at is None

    res = client.post(
        f"/api/v1/admin/organizations/{org.id}/delete",
        headers={"Authorization": f"Bearer {token}"},
        json={"confirmName": "Persist Delete Org"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "purge_scheduled_at" in body and "retention_days" in body
    assert "seats" not in body

    db_session.expire_all()
    after = db_session.get(Organization, org.id)
    assert after is not None
    assert after.deleted_at is not None
    assert after.purge_scheduled_at is not None

    listing = client.get("/api/v1/admin/organizations", headers={"Authorization": f"Bearer {token}"}).json()
    ids = [item["id"] for item in listing["items"]]
    assert str(org.id) not in ids
    assert listing["counts"]["pending_deletion"] >= 1

    pending = client.get(
        "/api/v1/admin/organizations?status=pending_deletion",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    assert str(org.id) in [item["id"] for item in pending["items"]]

    get_one = client.get(
        f"/api/v1/admin/organizations/{org.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_one.status_code == 404


def test_wrong_confirm_name_leaves_db_unchanged(client: TestClient, db_session):
    _super, token = _seed_super(db_session)
    org = Organization(name="Exact Name Only", slug="exact-only", license_limit=2, license_status="active", is_active=True)
    db_session.add(org)
    db_session.commit()

    res = client.post(
        f"/api/v1/admin/organizations/{org.id}/delete",
        headers={"Authorization": f"Bearer {token}"},
        json={"confirmName": "wrong"},
    )
    assert res.status_code == 400
    db_session.refresh(org)
    assert org.deleted_at is None


def test_member_remove_persists_hard_delete(client: TestClient, db_session):
    _super, token = _seed_super(db_session)
    org = Organization(name="Member Persist", slug="member-persist", license_limit=5, license_status="active", is_active=True)
    db_session.add(org)
    db_session.flush()
    admin = User(email="mpa@example.com", full_name="A", hashed_password=hash_password("x"), is_active=True)
    editor = User(email="mpe@example.com", full_name="E", hashed_password=hash_password("x"), is_active=True)
    db_session.add_all([admin, editor])
    db_session.flush()
    admin_m = OrganizationMembership(organization_id=org.id, user_id=admin.id, role=Role.ORG_ADMIN.value, is_active=True)
    editor_m = OrganizationMembership(organization_id=org.id, user_id=editor.id, role=Role.EDITOR.value, is_active=True)
    db_session.add_all([admin_m, editor_m])
    db_session.commit()
    editor_id = editor_m.id

    res = client.post(
        f"/api/v1/admin/organizations/{org.id}/members/{editor_id}/deactivate",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "persist test"},
    )
    assert res.status_code == 204

    assert db_session.get(OrganizationMembership, editor_id) is None

    directory = client.get(
        f"/api/v1/admin/organizations/{org.id}/directory",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    assert "mpe@example.com" not in [r["email"] for r in directory["rows"]]


def test_invitation_history_delete_removes_row(client: TestClient, db_session):
    super_user, token = _seed_super(db_session)
    org = Organization(name="Inv Persist", slug="inv-persist", license_limit=5, license_status="active", is_active=True)
    db_session.add(org)
    db_session.flush()
    _user, _m, invitation, _raw, _exp = provision_user_invitation(
        db_session,
        admin_user_id=super_user.id,
        organization_id=org.id,
        email="hist@example.com",
        full_name="Hist",
        role=Role.ORG_ADMIN,
    )
    db_session.commit()
    inv_id = invitation.id

    assert db_session.get(UserInvitation, inv_id) is not None

    res = client.post(
        f"/api/v1/admin/organizations/{org.id}/invitation-history/{inv_id}/delete",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 204

    assert db_session.get(UserInvitation, inv_id) is None

    history = client.get(
        f"/api/v1/admin/organizations/{org.id}/invitations/history",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    assert str(inv_id) not in [row["id"] for row in history]

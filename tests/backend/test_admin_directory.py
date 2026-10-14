"""Platform organization directory: members list and remove/revoke behavior."""

from __future__ import annotations

from fastapi.testclient import TestClient

from uuid import UUID

from app.core.jwt_audiences import AUD_PLATFORM
from app.core.platform_roles import PlatformRole
from app.core.roles import Role
from app.core.security import create_access_token, hash_password
from app.models.organization import Organization, User
from app.services.platform_provisioning import provision_user_invitation


def _platform_token(user: User) -> str:
    return create_access_token(
        str(user.id),
        {"aud": "aqrem-master", "platform_role": user.platform_role, "platform_auth_version": 1},
        audience=AUD_PLATFORM,
    )


def _seed_super_admin(db_session) -> tuple[User, str]:
    user = User(
        email="dir-super@test.local",
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


def _create_org(client: TestClient, token: str) -> str:
    res = client.post(
        "/api/v1/admin/organizations",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Directory Org", "license_limit": 10, "environment": "production"},
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _directory_emails(client: TestClient, token: str, org_id: str) -> list[str]:
    res = client.get(
        f"/api/v1/admin/organizations/{org_id}/directory",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200, res.text
    return [row["email"] for row in res.json()["rows"]]


def test_directory_dedupes_active_member_and_pending_invite(client: TestClient, db_session):
    _user, token = _seed_super_admin(db_session)
    org_id = _create_org(client, token)
    invite = client.post(
        f"/api/v1/admin/organizations/{org_id}/invitations/admin",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "pending@corp.example", "full_name": "Pending Admin", "expires_days": 7},
    )
    assert invite.status_code == 201, invite.text
    emails = _directory_emails(client, token, org_id)
    assert emails.count("pending@corp.example") == 1


def test_revoke_pending_invite_removes_directory_row(client: TestClient, db_session):
    _user, token = _seed_super_admin(db_session)
    org_id = _create_org(client, token)
    created = client.post(
        f"/api/v1/admin/organizations/{org_id}/invitations/admin",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "revoke@corp.example", "full_name": "Revoke Me", "expires_days": 7},
    )
    assert created.status_code == 201
    invitation_id = created.json()["invitation_id"]

    revoke = client.post(
        f"/api/v1/admin/organizations/{org_id}/invitations/{invitation_id}/revoke",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert revoke.status_code == 204

    emails = _directory_emails(client, token, org_id)
    assert "revoke@corp.example" not in emails


def test_deactivate_member_removes_row_and_pending_invite(client: TestClient, db_session):
    super_user, token = _seed_super_admin(db_session)
    org_id = _create_org(client, token)
    org = db_session.get(Organization, UUID(org_id))
    assert org is not None
    _user, membership, _invitation, _raw, _exp = provision_user_invitation(
        db_session,
        admin_user_id=super_user.id,
        organization_id=org.id,
        email="member@corp.example",
        full_name="Member One",
        role=Role.EDITOR,
    )
    db_session.commit()
    membership_id = str(membership.id)

    deactivate = client.post(
        f"/api/v1/admin/organizations/{org_id}/members/{membership_id}/deactivate",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "test remove"},
    )
    assert deactivate.status_code == 204

    emails = _directory_emails(client, token, org_id)
    assert "member@corp.example" not in emails

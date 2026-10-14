"""Member removal from organizations (platform + org admin)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.jwt_audiences import AUD_EMPLOYEE, AUD_ORG_ADMIN, AUD_PLATFORM
from app.core.platform_roles import PlatformRole
from app.core.roles import Role
from app.core.security import create_access_token, hash_password
from app.models.organization import Organization, OrganizationMembership, User
from app.services.platform_provisioning import provision_user_invitation


def _platform_token(user: User) -> str:
    return create_access_token(
        str(user.id),
        {"aud": "aqrem-master", "platform_role": user.platform_role, "platform_auth_version": 1},
        audience=AUD_PLATFORM,
    )


def _tenant_token(user_id: str, org_id: str, role: Role, auth_version: int = 1) -> str:
    aud = AUD_ORG_ADMIN if role == Role.ORG_ADMIN else AUD_EMPLOYEE
    return create_access_token(
        user_id,
        {"aud": aud, "organization_id": org_id, "role": role.value, "auth_version": auth_version},
        audience=aud,
    )


def _seed_super(db_session) -> tuple[User, str]:
    user = User(
        email="rm-super@test.local",
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


def test_remove_member_hard_deletes_and_updates_directory(client: TestClient, db_session):
    super_user, token = _seed_super(db_session)
    org = Organization(name="Rm Org", slug="rm-org", license_limit=5, license_status="active", is_active=True)
    db_session.add(org)
    db_session.flush()
    admin = User(email="admin@rm.example.com", full_name="Admin", hashed_password=hash_password("x"), is_active=True)
    editor = User(email="edit@rm.example.com", full_name="Editor", hashed_password=hash_password("x"), is_active=True)
    db_session.add_all([admin, editor])
    db_session.flush()
    admin_m = OrganizationMembership(organization_id=org.id, user_id=admin.id, role=Role.ORG_ADMIN.value, is_active=True)
    editor_m = OrganizationMembership(organization_id=org.id, user_id=editor.id, role=Role.EDITOR.value, is_active=True)
    db_session.add_all([admin_m, editor_m])
    db_session.commit()

    res = client.post(
        f"/api/v1/admin/organizations/{org.id}/members/{editor_m.id}/deactivate",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "no longer needed"},
    )
    assert res.status_code == 204, res.text

    directory = client.get(
        f"/api/v1/admin/organizations/{org.id}/directory",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    emails = [r["email"] for r in directory["rows"]]
    assert "edit@rm.example.com" not in emails
    assert directory["seats"]["active_members"] == 1

    assert db_session.get(OrganizationMembership, editor_m.id) is None


def test_cannot_remove_last_org_admin(client: TestClient, db_session):
    _super, token = _seed_super(db_session)
    org = Organization(name="Last Admin", slug="last-admin", license_limit=3, license_status="active", is_active=True)
    db_session.add(org)
    db_session.flush()
    admin = User(email="only@rm.example.com", full_name="Only", hashed_password=hash_password("x"), is_active=True)
    db_session.add(admin)
    db_session.flush()
    m = OrganizationMembership(organization_id=org.id, user_id=admin.id, role=Role.ORG_ADMIN.value, is_active=True)
    db_session.add(m)
    db_session.commit()

    res = client.post(
        f"/api/v1/admin/organizations/{org.id}/members/{m.id}/deactivate",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "try last admin"},
    )
    assert res.status_code == 409


def test_org_admin_cannot_remove_member_of_other_org(client: TestClient, db_session):
    org_a = Organization(name="A", slug="org-a-rm", license_limit=5, license_status="active", is_active=True)
    org_b = Organization(name="B", slug="org-b-rm", license_limit=5, license_status="active", is_active=True)
    db_session.add_all([org_a, org_b])
    db_session.flush()
    oa = User(email="oa@rm.example.com", full_name="OA", hashed_password=hash_password("x"), is_active=True)
    ob = User(email="ob@rm.example.com", full_name="OB", hashed_password=hash_password("x"), is_active=True)
    victim = User(email="v@rm.example.com", full_name="V", hashed_password=hash_password("x"), is_active=True)
    db_session.add_all([oa, ob, victim])
    db_session.flush()
    db_session.add_all(
        [
            OrganizationMembership(organization_id=org_a.id, user_id=oa.id, role=Role.ORG_ADMIN.value, is_active=True),
            OrganizationMembership(organization_id=org_b.id, user_id=ob.id, role=Role.ORG_ADMIN.value, is_active=True),
            OrganizationMembership(organization_id=org_b.id, user_id=victim.id, role=Role.EDITOR.value, is_active=True),
        ]
    )
    db_session.commit()
    victim_m = (
        db_session.query(OrganizationMembership)
        .filter(OrganizationMembership.user_id == victim.id, OrganizationMembership.organization_id == org_b.id)
        .one()
    )
    oa_tok = _tenant_token(str(oa.id), str(org_a.id), Role.ORG_ADMIN)
    res = client.post(
        f"/api/v1/org-admin/members/{victim_m.id}/deactivate",
        headers={"Authorization": f"Bearer {oa_tok}", "X-Organization-Id": str(org_a.id)},
    )
    assert res.status_code == 404


def test_normalize_drops_inactive_duplicate_org_admin(client: TestClient, db_session):
    _super, token = _seed_super(db_session)
    org = Organization(name="Dup Admin", slug="dup-admin", license_limit=5, license_status="active", is_active=True)
    db_session.add(org)
    db_session.flush()
    u1 = User(email="a1@dup.example.com", full_name="A1", hashed_password=hash_password("x"), is_active=True)
    u2 = User(email="a2@dup.example.com", full_name="A2", hashed_password=hash_password("x"), is_active=False)
    db_session.add_all([u1, u2])
    db_session.flush()
    db_session.add_all(
        [
            OrganizationMembership(organization_id=org.id, user_id=u1.id, role=Role.ORG_ADMIN.value, is_active=True),
            OrganizationMembership(organization_id=org.id, user_id=u2.id, role=Role.ORG_ADMIN.value, is_active=False),
        ]
    )
    db_session.commit()

    directory = client.get(
        f"/api/v1/admin/organizations/{org.id}/directory",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    admin_rows = [r for r in directory["rows"] if r.get("role") == "ORG_ADMIN"]
    assert len(admin_rows) == 1
    assert admin_rows[0]["email"] == "a1@dup.example.com"


def test_remove_releases_seat_after_provision_invite(client: TestClient, db_session):
    super_user, token = _seed_super(db_session)
    org = Organization(name="Seat Org", slug="seat-org", license_limit=5, license_status="active", is_active=True)
    db_session.add(org)
    db_session.flush()
    _user, membership, _inv, _raw, _exp = provision_user_invitation(
        db_session,
        admin_user_id=super_user.id,
        organization_id=org.id,
        email="seat@rm.example.com",
        full_name="Seat User",
        role=Role.EDITOR,
    )
    db_session.commit()
    before = client.get(
        f"/api/v1/admin/organizations/{org.id}/directory",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    assert before["seats"]["seats_used"] >= 1

    client.post(
        f"/api/v1/admin/organizations/{org.id}/members/{membership.id}/deactivate",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "release seat"},
    )
    after = client.get(
        f"/api/v1/admin/organizations/{org.id}/directory",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    assert after["seats"]["active_members"] == 0

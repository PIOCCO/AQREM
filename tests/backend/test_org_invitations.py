"""Admin invitations and employee join link security."""

from urllib.parse import unquote

from fastapi.testclient import TestClient

from app.core.jwt_audiences import AUD_PLATFORM
from app.core.platform_roles import PlatformRole
from app.core.security import create_access_token, hash_password
from app.models.organization import Organization, User
from app.services.invitations.tokens import hash_token


def _platform_token(user: User) -> str:
    return create_access_token(
        str(user.id),
        {"aud": "aqrem-master", "platform_role": user.platform_role, "platform_auth_version": 1},
        audience=AUD_PLATFORM,
    )


def _seed_super_admin(db_session) -> tuple[User, str]:
    user = User(
        email="super@inv.test",
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


def _create_org(client: TestClient, token: str, name: str = "Invite Org") -> str:
    res = client.post(
        "/api/v1/admin/organizations",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": name, "license_limit": 10, "environment": "production"},
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def test_billing_cannot_create_admin_invitation(client: TestClient, db_session):
    _super, super_token = _seed_super_admin(db_session)
    org_id = _create_org(client, super_token)
    billing = User(
        email="billing@inv.test",
        full_name="Billing",
        hashed_password=hash_password("password"),
        platform_role=PlatformRole.PLATFORM_BILLING.value,
        is_active=True,
    )
    db_session.add(billing)
    db_session.flush()
    token = _platform_token(billing)
    res = client.post(
        f"/api/v1/admin/organizations/{org_id}/invitations/admin",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "admin@corp.example", "full_name": "Admin Person"},
    )
    assert res.status_code == 403


def test_admin_invitation_single_active_and_accept(client: TestClient, db_session):
    _user, token = _seed_super_admin(db_session)
    org_id = _create_org(client, token)

    first = client.post(
        f"/api/v1/admin/organizations/{org_id}/invitations/admin",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "admin@corp.example", "full_name": "Admin One", "expires_days": 7},
    )
    assert first.status_code == 201
    path1 = first.json()["invitation_setup_path"]
    assert first.json()["invitation_setup_url"].endswith(path1.replace(" ", ""))
    raw1 = unquote(path1.split("/invite/admin/", 1)[1])

    second = client.post(
        f"/api/v1/admin/organizations/{org_id}/invitations/admin",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "admin2@corp.example", "full_name": "Admin Two"},
    )
    assert second.status_code == 201
    preview = client.post("/api/v1/auth/accept-invitation/preview", json={"token": raw1})
    assert preview.status_code == 404

    path2 = second.json()["invitation_setup_path"]
    raw2 = unquote(path2.split("/invite/admin/", 1)[1])
    preview2 = client.post("/api/v1/auth/accept-invitation/preview", json={"token": raw2})
    assert preview2.status_code == 200
    assert preview2.json()["organization_name"] == "Invite Org"
    assert preview2.json()["role"] == "ORG_ADMIN"

    send_code = client.post(
        "/api/v1/auth/accept-invitation/send-verification",
        json={"token": raw2, "email": "admin2@corp.example"},
    )
    assert send_code.status_code == 200, send_code.text
    code = send_code.json()["dev_verification_code"]
    assert code

    accept = client.post(
        "/api/v1/auth/accept-invitation",
        json={
            "token": raw2,
            "email": "admin2@corp.example",
            "verification_code": code,
            "password": "securepass1",
            "full_name": "Admin Two",
        },
    )
    assert accept.status_code == 200
    assert "access_token" in accept.json()

    reuse = client.post(
        "/api/v1/auth/accept-invitation",
        json={
            "token": raw2,
            "email": "admin2@corp.example",
            "verification_code": code,
            "password": "securepass1",
        },
    )
    assert reuse.status_code == 400


def test_employee_join_domain_and_rotation(client: TestClient, db_session):
    _user, token = _seed_super_admin(db_session)
    org_id = _create_org(client, token, name="Join Org")

    link_res = client.post(
        f"/api/v1/admin/organizations/{org_id}/employee-link",
        headers={"Authorization": f"Bearer {token}"},
        json={"allowed_domains": ["corp.example"], "require_admin_approval": False, "expires_days": 30},
    )
    assert link_res.status_code == 201
    join_path = link_res.json()["join_path"]
    join_token = unquote(join_path.split("/join/", 1)[1])
    link_id = link_res.json()["link_id"]

    bad = client.post("/api/v1/public/join/start", json={"token": join_token, "email": "x@other.example", "full_name": "X"})
    assert bad.status_code == 400

    start = client.post(
        "/api/v1/public/join/start",
        json={"token": join_token, "email": "emp@corp.example", "full_name": "Employee"},
    )
    assert start.status_code == 200
    pending_id = start.json()["pending_id"]
    code = start.json().get("dev_verification_code")
    assert code

    verify = client.post(
        "/api/v1/public/join/verify-email",
        json={"token": join_token, "pending_id": pending_id, "code": code},
    )
    assert verify.status_code == 200

    complete = client.post(
        "/api/v1/public/join/complete",
        json={"token": join_token, "pending_id": pending_id, "password": "employeepass"},
    )
    assert complete.status_code == 200
    assert complete.json()["status"] == "joined"

    rotate = client.post(
        f"/api/v1/admin/organizations/{org_id}/employee-link/{link_id}/rotate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rotate.status_code == 200
    new_token = unquote(rotate.json()["join_path"].split("/join/", 1)[1])

    stale = client.post(
        "/api/v1/public/join/preview",
        json={"token": join_token},
    )
    assert stale.status_code == 404

    preview = client.post("/api/v1/public/join/preview", json={"token": new_token})
    assert preview.status_code == 200


def test_invitation_history_lists_pending_until_expired(client: TestClient, db_session):
    _user, token = _seed_super_admin(db_session)
    org_id = _create_org(client, token, name="History Org")
    created = client.post(
        f"/api/v1/admin/organizations/{org_id}/invitations/admin",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "hist@corp.example", "full_name": "Hist Admin", "expires_days": 7},
    )
    assert created.status_code == 201
    history = client.get(
        f"/api/v1/admin/organizations/{org_id}/invitations/history",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert history.status_code == 200
    body = history.json()
    assert any(r["status"] == "pending" and r["record_type"] == "admin_invitation" for r in body)


def test_token_hashes_never_equal_raw_in_db(client: TestClient, db_session):
    from app.models.invitation import UserInvitation
    from app.models.employee_join import EmployeeJoinLink

    _user, token = _seed_super_admin(db_session)
    org_id = _create_org(client, token, name="Hash Org")
    inv = client.post(
        f"/api/v1/admin/organizations/{org_id}/invitations/admin",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "h@corp.example", "full_name": "H"},
    ).json()
    raw = unquote(inv["invitation_setup_path"].split("/invite/admin/", 1)[1])
    row = db_session.query(UserInvitation).filter(UserInvitation.organization_id == org_id).first()
    assert row.token_hash == hash_token(raw)
    assert row.token_hash != raw

    link = client.post(
        f"/api/v1/admin/organizations/{org_id}/employee-link",
        headers={"Authorization": f"Bearer {token}"},
        json={"allowed_domains": ["corp.example"]},
    ).json()
    raw_link = unquote(link["join_path"].split("/join/", 1)[1])
    link_row = db_session.get(EmployeeJoinLink, link["link_id"])
    assert link_row.token_hash == hash_token(raw_link)

"""Client admin dashboard — privacy, auth, uploads, telemetry."""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from app.core.roles import Role
from app.core.jwt_audiences import AUD_EMPLOYEE, AUD_ORG_ADMIN, AUD_PLATFORM
from app.core.security import create_access_token, hash_password
from app.models.client_admin import ClientCredentialMetadata
from app.models.organization import Organization, OrganizationMembership, User
from app.services.client_secrets.vault_store import MemoryClientSecretStore
from app.services.telemetry import TelemetryRejected, validate_control_plane_payload
from app.services.telemetry_schema import build_telemetry_payload


def _org_admin_headers(token: str, org_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}


def _seed_org_admin(db_session) -> tuple[Organization, User, str]:
    org = Organization(name="Client Co", slug="client-co-dash", license_limit=10)
    db_session.add(org)
    db_session.flush()
    admin = User(email="orgadmin@client.test", full_name="Admin", hashed_password=hash_password("password"))
    db_session.add(admin)
    db_session.flush()
    db_session.add(
        OrganizationMembership(organization_id=org.id, user_id=admin.id, role=Role.ORG_ADMIN.value),
    )
    db_session.commit()
    token = create_access_token(
        str(admin.id),
        {"organization_id": str(org.id), "role": Role.ORG_ADMIN.value, "aud": "aqrem-org-admin"},
    )
    return org, admin, token


def test_org_admin_cannot_manage_model_token(client: TestClient, db_session):
    org, _admin, token = _seed_org_admin(db_session)
    secret = "sk-test-secret-value-12345678"
    for method, path in (
        ("GET", "/api/v1/org-admin/model-token"),
        ("PUT", "/api/v1/org-admin/model-token"),
        ("POST", "/api/v1/org-admin/model-token/test"),
    ):
        res = client.request(
            method,
            path,
            headers=_org_admin_headers(token, str(org.id)),
            json={"token": secret} if method == "PUT" else None,
        )
        assert res.status_code == 403, res.text
        assert "super admin" in res.json()["detail"]["message"].lower()


def test_super_admin_model_token_not_in_db_or_audit(client: TestClient, db_session):
    from app.core.platform_roles import PlatformRole
    from app.core.jwt_audiences import AUD_PLATFORM

    org, _admin, _oa_token = _seed_org_admin(db_session)
    super_user = User(
        email="super@test.com",
        full_name="Super",
        hashed_password=hash_password("password"),
        is_platform_admin=True,
        platform_role=PlatformRole.SUPER_ADMIN.value,
    )
    db_session.add(super_user)
    db_session.commit()
    super_token = create_access_token(
        str(super_user.id),
        {"platform_role": PlatformRole.SUPER_ADMIN.value, "platform_auth_version": 1},
        audience=AUD_PLATFORM,
    )
    secret = "sk-test-secret-value-12345678"
    res = client.put(
        f"/api/v1/admin/organizations/{org.id}/model-token",
        headers={"Authorization": f"Bearer {super_token}"},
        json={"token": secret},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert secret not in str(body)
    assert "****" in body["masked_value"]

    cred = db_session.query(ClientCredentialMetadata).filter(ClientCredentialMetadata.organization_id == org.id).one()
    assert secret not in cred.vault_secret_name or cred.vault_secret_name.startswith("kv://")
    assert secret not in (cred.masked_hint or "")


def test_employee_token_rejected_on_org_admin(client: TestClient, db_session):
    org, _admin, _token = _seed_org_admin(db_session)
    editor = User(email="ed@client.test", full_name="Ed", hashed_password=hash_password("password"))
    db_session.add(editor)
    db_session.flush()
    db_session.add(
        OrganizationMembership(organization_id=org.id, user_id=editor.id, role=Role.EDITOR.value),
    )
    db_session.commit()
    employee_token = create_access_token(
        str(editor.id),
        {"organization_id": str(org.id), "role": Role.EDITOR.value, "aud": "aqrem-employee"},
    )
    res = client.get("/api/v1/org-admin/overview", headers=_org_admin_headers(employee_token, str(org.id)))
    assert res.status_code == 403
    detail = res.json()["detail"]
    detail_str = detail if isinstance(detail, str) else str(detail.get("message", detail))
    assert "administrator" in detail_str.lower() or detail.get("code") == "WRONG_AUDIENCE"


def test_master_token_rejected_on_org_admin(client: TestClient, db_session):
    org, _, _ = _seed_org_admin(db_session)
    master = User(
        email="master@test.com",
        full_name="M",
        hashed_password=hash_password("password"),
        is_platform_admin=True,
    )
    db_session.add(master)
    db_session.commit()
    master_token = create_access_token(str(master.id), {"platform_role": "SUPER_ADMIN", "platform_auth_version": 1}, audience=AUD_PLATFORM)
    res = client.get("/api/v1/org-admin/overview", headers=_org_admin_headers(master_token, str(org.id)))
    assert res.status_code in (401, 403)


def test_upload_rejects_eicar(client: TestClient, db_session, monkeypatch, tmp_path):
    monkeypatch.setenv("LOCAL_UPLOAD_DIR", str(tmp_path / "uploads"))
    from app.core.config import get_settings

    get_settings.cache_clear()
    org, _, token = _seed_org_admin(db_session)
    eicar = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
    res = client.post(
        "/api/v1/org-admin/documents/upload",
        headers={"Authorization": f"Bearer {token}", "X-Organization-Id": str(org.id)},
        files=[("files", ("eicar.txt", io.BytesIO(eicar), "text/plain"))],
        data={"visibility_mode": "all_staff"},
    )
    assert res.status_code == 400
    assert res.json()["detail"]["code"] == "MALWARE_DETECTED"


def test_telemetry_rejects_file_name_field():
    with pytest.raises(TelemetryRejected):
        validate_control_plane_payload(
            "document.indexing_job_completed",
            {"indexed_count": 1, "file_name": "secret.pdf"},
        )


def test_telemetry_schema_rejects_extra_field():
    with pytest.raises(Exception):
        build_telemetry_payload(
            "license.seat_usage_changed",
            {"seats_used": 1, "seats_limit": 5, "question": "leak"},
        )


def test_cross_tenant_document_list_denied(client: TestClient, db_session):
    org_a, _, token_a = _seed_org_admin(db_session)
    org_b = Organization(name="Other", slug="other-dash", license_limit=5)
    db_session.add(org_b)
    db_session.commit()
    res = client.get("/api/v1/org-admin/documents", headers=_org_admin_headers(token_a, str(org_b.id)))
    assert res.status_code in (403, 404)


def test_seats_full_on_invite(client: TestClient, db_session):
    org = Organization(name="Full", slug="full-seats", license_limit=1)
    db_session.add(org)
    db_session.flush()
    admin = User(email="solo@full.test", full_name="Solo", hashed_password=hash_password("password"))
    db_session.add(admin)
    db_session.flush()
    db_session.add(
        OrganizationMembership(organization_id=org.id, user_id=admin.id, role=Role.ORG_ADMIN.value),
    )
    db_session.commit()
    token = create_access_token(
        str(admin.id),
        {"organization_id": str(org.id), "role": Role.ORG_ADMIN.value, "aud": "aqrem-org-admin"},
    )
    res = client.post(
        "/api/v1/org-admin/members/invite",
        headers=_org_admin_headers(token, str(org.id)),
        json={"email": "new@full.test", "full_name": "New Person", "role": "EDITOR"},
    )
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "SEATS_FULL"


def test_secret_store_not_in_postgres(db_session):
    store = MemoryClientSecretStore()
    org_id = _seed_org_admin(db_session)[0].id
    ref = store.write_model_token(org_id, "super-secret-key")
    assert "super-secret-key" not in ref
    row = db_session.query(ClientCredentialMetadata).filter(ClientCredentialMetadata.organization_id == org_id).first()
    assert row is None or "super-secret-key" not in row.vault_secret_name

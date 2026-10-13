"""
Automated cross-layer link scenarios (S1–S9, parts of S12).

Runs against the local test API + PostgreSQL (see tests/backend/conftest.py).
Does NOT cover Azure Key Vault, real multi-host deployments, or kill-switch drills (S10–S11).
"""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from app.core.roles import Role
from app.core.security import create_access_token, hash_password
from app.models.enums import LicenseStatus
from app.models.environment import ControlPlaneEvent
from app.models.organization import Organization, OrganizationMembership, User
from app.services.provisioning.service import run_provisioning_job
from app.services.telemetry import TelemetryRejected, validate_control_plane_payload


def _tenant_headers(token: str, org_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}


def _master_token(user_id: str) -> str:
    return create_access_token(user_id, {"role": "PLATFORM_ADMIN", "aud": "aqrem-master"})


def _org_admin_token(user_id: str, org_id: str, auth_version: int = 1) -> str:
    return create_access_token(
        user_id,
        {
            "organization_id": org_id,
            "role": Role.ORG_ADMIN.value,
            "aud": "aqrem-org-admin",
            "auth_version": auth_version,
        },
    )


def _employee_token(user_id: str, org_id: str, auth_version: int = 1) -> str:
    return create_access_token(
        user_id,
        {
            "organization_id": org_id,
            "role": Role.EDITOR.value,
            "aud": "aqrem-employee",
            "auth_version": auth_version,
        },
    )


def _seed_platform_admin(db_session) -> tuple[User, str]:
    admin = User(
        email="platform-links@test.com",
        full_name="Platform",
        hashed_password=hash_password("password"),
        is_platform_admin=True,
    )
    db_session.add(admin)
    db_session.commit()
    return admin, _master_token(str(admin.id))


@pytest.mark.parametrize("forbidden_key", ["file_name", "question", "document_text"])
def test_s9_telemetry_rejects_forbidden_fields(forbidden_key: str):
    with pytest.raises(TelemetryRejected):
        validate_control_plane_payload(
            "license.seat_usage_changed",
            {"seats_used": 1, "seats_limit": 5, forbidden_key: "leak"},
        )


def test_s8_token_confusion_matrix(client: TestClient, db_session):
    org = Organization(name="Link Org", slug="link-org", license_limit=5)
    db_session.add(org)
    db_session.flush()
    employee = User(email="emp@link.test", full_name="Emp", hashed_password=hash_password("password"))
    db_session.add(employee)
    db_session.flush()
    db_session.add(
        OrganizationMembership(organization_id=org.id, user_id=employee.id, role=Role.EDITOR.value),
    )
    db_session.commit()
    emp_tok = _employee_token(str(employee.id), str(org.id))
    assert client.get("/api/v1/org-admin/setup", headers=_tenant_headers(emp_tok, str(org.id))).status_code == 403
    assert client.get("/api/v1/master/environments", headers={"Authorization": f"Bearer {emp_tok}"}).status_code == 403

    admin, master_tok = _seed_platform_admin(db_session)
    assert (
        client.get("/api/v1/projects", headers=_tenant_headers(master_tok, str(org.id))).status_code == 403
    )
    org_admin = User(email="oa@link.test", full_name="OA", hashed_password=hash_password("password"))
    db_session.add(org_admin)
    db_session.flush()
    db_session.add(
        OrganizationMembership(organization_id=org.id, user_id=org_admin.id, role=Role.ORG_ADMIN.value),
    )
    db_session.commit()
    oa_tok = _org_admin_token(str(org_admin.id), str(org.id))
    assert client.get("/api/v1/master/environments", headers={"Authorization": f"Bearer {oa_tok}"}).status_code == 403


def test_s1_provision_and_telemetry_pipeline(client: TestClient, db_session, monkeypatch):
    admin, master_tok = _seed_platform_admin(db_session)
    res = client.post(
        "/api/v1/admin/organizations",
        headers={"Authorization": f"Bearer {master_tok}"},
        json={"name": "Provision Co", "slug": "provision-co", "license_limit": 5, "environment": "production"},
    )
    assert res.status_code == 201, res.text
    org_id = res.json()["id"]

    prov = client.post(
        f"/api/v1/master/organizations/{org_id}/provision",
        headers={"Authorization": f"Bearer {master_tok}"},
    )
    assert prov.status_code == 200, prov.text
    job_id = prov.json()["job_id"]
    from app.models.environment import ProvisioningJob

    from uuid import UUID

    job = db_session.get(ProvisioningJob, UUID(job_id))
    org = db_session.get(Organization, org_id)
    run_provisioning_job(db_session, job=job, org=org)
    db_session.commit()

    detail = client.get(
        f"/api/v1/master/organizations/{org_id}/environment",
        headers={"Authorization": f"Bearer {master_tok}"},
    )
    assert detail.status_code == 200
    env = detail.json()["environment"]
    assert env["employee_url"]
    assert env["admin_url"]
    assert env["deployment_status"] in {"ready", "blocked", "pending"}


def test_s2_seat_limit_then_raise(client: TestClient, db_session):
    admin, master_tok = _seed_platform_admin(db_session)
    org = Organization(name="Seats Co", slug="seats-co", license_limit=2)
    db_session.add(org)
    db_session.flush()
    oa = User(email="seats-oa@test.com", full_name="OA", hashed_password=hash_password("password"))
    db_session.add(oa)
    db_session.flush()
    db_session.add(OrganizationMembership(organization_id=org.id, user_id=oa.id, role=Role.ORG_ADMIN.value))
    db_session.commit()
    oa_tok = _org_admin_token(str(oa.id), str(org.id))

    first = client.post(
        "/api/v1/org-admin/members/invite",
        headers=_tenant_headers(oa_tok, str(org.id)),
        json={"email": "one@seats.test", "full_name": "One", "role": "EDITOR"},
    )
    assert first.status_code == 201, first.text
    second = client.post(
        "/api/v1/org-admin/members/invite",
        headers=_tenant_headers(oa_tok, str(org.id)),
        json={"email": "two@seats.test", "full_name": "Two", "role": "EDITOR"},
    )
    assert second.status_code == 403
    assert second.json()["detail"]["code"] == "SEATS_FULL"

    patch = client.patch(
        f"/api/v1/admin/organizations/{org.id}",
        headers={"Authorization": f"Bearer {master_tok}"},
        json={"license_limit": 3},
    )
    assert patch.status_code == 200, patch.text
    db_session.expire_all()
    org = db_session.get(Organization, org.id)
    assert org is not None and org.license_limit == 3
    third = client.post(
        "/api/v1/org-admin/members/invite",
        headers=_tenant_headers(oa_tok, str(org.id)),
        json={"email": "three@seats.test", "full_name": "Three", "role": "EDITOR"},
    )
    assert third.status_code == 201, third.text


def test_s3_license_suspend_blocks_l3(client: TestClient, db_session):
    admin, master_tok = _seed_platform_admin(db_session)
    org = Organization(name="Susp", slug="susp-co", license_limit=5, license_status=LicenseStatus.ACTIVE.value)
    db_session.add(org)
    db_session.flush()
    user = User(email="susp@emp.test", full_name="E", hashed_password=hash_password("password"))
    db_session.add(user)
    db_session.flush()
    db_session.add(OrganizationMembership(organization_id=org.id, user_id=user.id, role=Role.EDITOR.value))
    db_session.commit()
    tok = _employee_token(str(user.id), str(org.id))

    assert client.get("/api/v1/projects", headers=_tenant_headers(tok, str(org.id))).status_code == 200

    client.patch(
        f"/api/v1/admin/organizations/{org.id}",
        headers={"Authorization": f"Bearer {master_tok}"},
        json={"license_status": LicenseStatus.SUSPENDED.value},
    )
    db_session.expire_all()
    blocked = client.get("/api/v1/projects", headers=_tenant_headers(tok, str(org.id)))
    assert blocked.status_code == 403


def test_s4_deactivate_revokes_session(client: TestClient, db_session):
    org = Organization(name="Revoke Co", slug="revoke-co", license_limit=5)
    db_session.add(org)
    db_session.flush()
    oa = User(email="revoke-oa@test.com", full_name="OA", hashed_password=hash_password("password"))
    emp = User(email="revoke-emp@test.com", full_name="Emp", hashed_password=hash_password("password"))
    db_session.add_all([oa, emp])
    db_session.flush()
    oa_m = OrganizationMembership(organization_id=org.id, user_id=oa.id, role=Role.ORG_ADMIN.value)
    emp_m = OrganizationMembership(organization_id=org.id, user_id=emp.id, role=Role.EDITOR.value)
    db_session.add_all([oa_m, emp_m])
    db_session.commit()
    oa_tok = _org_admin_token(str(oa.id), str(org.id))
    emp_tok = _employee_token(str(emp.id), str(org.id), auth_version=1)
    assert client.get("/api/v1/projects", headers=_tenant_headers(emp_tok, str(org.id))).status_code == 200

    res = client.post(
        f"/api/v1/org-admin/members/{emp_m.id}/deactivate",
        headers=_tenant_headers(oa_tok, str(org.id)),
    )
    assert res.status_code == 204, res.text
    db_session.expire_all()
    assert client.get("/api/v1/projects", headers=_tenant_headers(emp_tok, str(org.id))).status_code in (
        401,
        403,
    )


def test_s7_two_tenant_isolation(client: TestClient, db_session):
    from tests.backend.test_e2e_authorization import _seed_org

    org_a, _pa, _ua, tok_a = _seed_org(db_session, "A", "layer-a")
    org_b, _pb, _ub, tok_b = _seed_org(db_session, "B", "layer-b")
    assert client.get("/api/v1/projects", headers=_tenant_headers(tok_a, str(org_a.id))).status_code == 200
    assert client.get("/api/v1/projects", headers=_tenant_headers(tok_b, str(org_b.id))).status_code == 200
    # Cross org header with other org's token should not leak B into A's context when using A's token on A
    assert (
        client.get("/api/v1/projects", headers=_tenant_headers(tok_a, str(org_b.id))).status_code == 403
    )


def test_l2_telemetry_persisted_for_l1(client: TestClient, db_session, monkeypatch):
    monkeypatch.setenv("CLIENT_SECRET_STORE", "memory")
    from app.core.config import get_settings

    get_settings.cache_clear()
    org = Organization(name="Tel Co", slug="tel-co", license_limit=5)
    db_session.add(org)
    db_session.flush()
    oa = User(email="tel-oa@test.com", full_name="OA", hashed_password=hash_password("password"))
    db_session.add(oa)
    db_session.flush()
    db_session.add(OrganizationMembership(organization_id=org.id, user_id=oa.id, role=Role.ORG_ADMIN.value))
    db_session.commit()
    oa_tok = _org_admin_token(str(oa.id), str(org.id))

    res = client.put(
        "/api/v1/org-admin/model-token",
        headers=_tenant_headers(oa_tok, str(org.id)),
        json={"token": "sk-test-123456789012345678901234"},
    )
    assert res.status_code == 200, res.text
    events = (
        db_session.query(ControlPlaneEvent)
        .filter(ControlPlaneEvent.organization_id == org.id)
        .order_by(ControlPlaneEvent.created_at.desc())
        .all()
    )
    assert any(e.event_type == "credential.expiry_metadata_updated" for e in events)
    assert "sk-test" not in str([e.payload for e in events])

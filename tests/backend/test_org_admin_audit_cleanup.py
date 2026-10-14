"""Org-admin audit log cleanup and console-enter dedupe."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.jwt_audiences import AUD_EMPLOYEE, AUD_ORG_ADMIN
from app.core.roles import Role
from app.core.security import create_access_token, hash_password
from app.models.audit import AuditEvent
from app.models.organization import Organization, OrganizationMembership, User


def _headers(token: str, org_id: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "X-Organization-Id": org_id,
        "Origin": "http://testserver",
        "X-Requested-With": "AQREM",
    }


def _seed_org_admin(db_session) -> tuple[Organization, User, str]:
    org = Organization(name="Audit Org", slug=f"aud-{uuid4().hex[:8]}", license_limit=5)
    db_session.add(org)
    db_session.flush()
    admin = User(email=f"oa-{uuid4().hex[:6]}@test.local", full_name="Admin", hashed_password=hash_password("x"), is_active=True)
    db_session.add(admin)
    db_session.flush()
    db_session.add(OrganizationMembership(organization_id=org.id, user_id=admin.id, role=Role.ORG_ADMIN.value))
    db_session.commit()
    token = create_access_token(
        str(admin.id),
        {"organization_id": str(org.id), "role": Role.ORG_ADMIN.value, "aud": "aqrem-org-admin"},
        audience=AUD_ORG_ADMIN,
    )
    return org, admin, token


def _seed_editor(db_session, org: Organization) -> str:
    user = User(email=f"ed-{uuid4().hex[:6]}@test.local", full_name="Ed", hashed_password=hash_password("x"), is_active=True)
    db_session.add(user)
    db_session.flush()
    db_session.add(OrganizationMembership(organization_id=org.id, user_id=user.id, role=Role.EDITOR.value))
    db_session.commit()
    return create_access_token(
        str(user.id),
        {"organization_id": str(org.id), "role": Role.EDITOR.value, "aud": "aqrem-employee"},
        audience=AUD_EMPLOYEE,
    )


def test_cleanup_older_than_30d_leaves_recent_and_writes_audit_row(client: TestClient, db_session):
    org, admin, token = _seed_org_admin(db_session)
    old = AuditEvent(
        organization_id=org.id,
        user_id=admin.id,
        action="member_invited",
        resource_type="invitation",
        resource_id="x",
        event_metadata={},
    )
    db_session.add(old)
    db_session.flush()
    db_session.execute(
        AuditEvent.__table__.update()
        .where(AuditEvent.id == old.id)
        .values(created_at=datetime.now(UTC) - timedelta(days=40))
    )
    recent = AuditEvent(
        organization_id=org.id,
        user_id=admin.id,
        action="member_invited",
        resource_type="invitation",
        resource_id="y",
        event_metadata={},
    )
    db_session.add(recent)
    db_session.commit()

    res = client.delete(
        "/api/v1/org-admin/audit-logs?scope=older_than_30d",
        headers=_headers(token, str(org.id)),
    )
    assert res.status_code == 200, res.text
    assert res.json()["deleted_count"] == 1

    listing = client.get("/api/v1/org-admin/audit", headers=_headers(token, str(org.id))).json()
    actions = [i["action"] for i in listing["items"]]
    assert any("audit logs cleaned up" in a for a in actions)
    assert listing["total"] >= 2


def test_editor_forbidden_cleanup(client: TestClient, db_session):
    org, _, _ = _seed_org_admin(db_session)
    editor_tok = _seed_editor(db_session, org)
    res = client.delete(
        "/api/v1/org-admin/audit-logs?scope=older_than_7d",
        headers=_headers(editor_tok, str(org.id)),
    )
    assert res.status_code == 403


def test_invalid_scope_returns_400(client: TestClient, db_session):
    org, _, token = _seed_org_admin(db_session)
    res = client.delete(
        "/api/v1/org-admin/audit-logs?scope=older_than_1y",
        headers=_headers(token, str(org.id)),
    )
    assert res.status_code == 400
    assert res.json()["detail"]["code"] == "INVALID_SCOPE"


def test_cross_org_isolation(client: TestClient, db_session):
    org_a, admin_a, tok_a = _seed_org_admin(db_session)
    org_b, _, tok_b = _seed_org_admin(db_session)
    db_session.add(
        AuditEvent(
            organization_id=org_b.id,
            user_id=admin_a.id,
            action="test_event",
            resource_type="test",
            resource_id="1",
            event_metadata={},
        )
    )
    db_session.commit()
    before_b = client.get("/api/v1/org-admin/audit", headers=_headers(tok_b, str(org_b.id))).json()["total"]
    client.delete(
        "/api/v1/org-admin/audit-logs?scope=all",
        headers=_headers(tok_a, str(org_a.id)),
    )
    after_b = client.get("/api/v1/org-admin/audit", headers=_headers(tok_b, str(org_b.id))).json()["total"]
    assert after_b == before_b


def test_batch_cleanup_many_rows(client: TestClient, db_session, monkeypatch):
    from app.services.audit import org_cleanup

    monkeypatch.setattr(org_cleanup, "BATCH_SIZE", 50)
    org, admin, token = _seed_org_admin(db_session)
    for i in range(120):
        db_session.add(
            AuditEvent(
                organization_id=org.id,
                user_id=admin.id,
                action="noise_event",
                resource_type="test",
                resource_id=str(i),
                event_metadata={},
            )
        )
    db_session.commit()
    res = client.delete(
        "/api/v1/org-admin/audit-logs?scope=all",
        headers=_headers(token, str(org.id)),
    )
    assert res.status_code == 200
    assert res.json()["deleted_count"] == 120
    listing = client.get("/api/v1/org-admin/audit", headers=_headers(token, str(org.id))).json()
    assert listing["total"] == 1
    assert "audit logs cleaned up" in listing["items"][0]["action"]


def test_console_enter_deduped(client: TestClient, db_session):
    org, admin, token = _seed_org_admin(db_session)
    h = _headers(token, str(org.id))
    assert client.get("/api/v1/org-admin/console-enter", headers=h).status_code == 200
    assert client.get("/api/v1/org-admin/console-enter", headers=h).status_code == 200
    listing = client.get("/api/v1/org-admin/audit", headers=h).json()
    entered = [i for i in listing["items"] if "admin console entered" in i["action"]]
    assert len(entered) == 1

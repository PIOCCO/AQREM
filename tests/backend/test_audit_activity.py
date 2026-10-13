from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.audit.service import record_audit
from app.core.roles import Role
from app.core.jwt_audiences import AUD_EMPLOYEE, AUD_ORG_ADMIN, AUD_PLATFORM
from app.core.security import create_access_token, hash_password
from app.models.organization import Organization, OrganizationMembership, User


def _auth(token: str, org_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}


def _seed(db_session, slug: str):
    org = Organization(name=f"Org {slug}", slug=slug, license_limit=5)
    db_session.add(org)
    db_session.flush()
    actor = User(email=f"actor-{slug}@example.com", hashed_password=hash_password("x"), full_name="Ada Actor")
    db_session.add(actor)
    db_session.flush()
    db_session.add(OrganizationMembership(organization_id=org.id, user_id=actor.id, role=Role.EDITOR.value))
    db_session.flush()
    token = create_access_token(str(actor.id), {"organization_id": str(org.id), "role": Role.EDITOR.value})
    return org, actor, token


def test_activity_enrichment_and_tenant_isolation(client: TestClient, db_session):
    org_a, actor_a, token_a = _seed(db_session, "act-a")
    org_b, _actor_b, token_b = _seed(db_session, "act-b")

    record_audit(
        db_session,
        organization_id=org_a.id,
        user_id=actor_a.id,
        action="user_invited",
        resource_type="invitation",
        resource_id="inv-1",
        metadata={"email": "new@example.com", "role": "VIEWER"},
    )
    record_audit(
        db_session,
        organization_id=org_b.id,
        user_id=None,
        action="organization_created",
        resource_type="organization",
        resource_id=str(org_b.id),
        metadata={},
    )
    db_session.commit()

    res = client.get("/api/v1/audit", headers=_auth(token_a, str(org_a.id)))
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert "Ada Actor" in item["summary"]
    assert "new@example.com" in item["summary"]
    assert item["actor_email"] == actor_a.email
    assert "new@example.com" not in item["summary"] or "invited" in item["summary"]

    other = client.get("/api/v1/audit", headers=_auth(token_b, str(org_b.id)))
    assert other.json()["total"] == 1
    assert other.json()["items"][0]["action"] == "organization_created"

    cross = client.get("/api/v1/audit", headers=_auth(token_b, str(org_b.id)))
    assert all(row["id"] != item["id"] for row in cross.json()["items"])


def test_activity_search_and_date_filter(client: TestClient, db_session):
    org, actor, token = _seed(db_session, "act-filter")
    old = datetime.now(timezone.utc) - timedelta(days=10)
    record_audit(
        db_session,
        organization_id=org.id,
        user_id=actor.id,
        action="questionnaire_created",
        resource_type="questionnaire",
        resource_id="q1",
        metadata={},
    )
    db_session.commit()
    res = client.get(
        "/api/v1/audit",
        headers=_auth(token, str(org.id)),
        params={"search": "questionnaire", "actions": ["questionnaire_created"]},
    )
    assert res.status_code == 200
    assert res.json()["total"] >= 1
    assert res.json()["items"][0]["summary"]

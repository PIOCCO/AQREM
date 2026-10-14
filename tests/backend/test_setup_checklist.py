"""Setup checklist: PostgreSQL requires explicit org-admin validation."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.roles import Role
from app.core.security import create_access_token, hash_password
from app.models.organization import Organization, OrganizationMembership, User
from app.models.tenant_data_store import TenantDataStoreConfig
from app.services.setup_checklist import build_setup_checklist
from app.tenant_store.resolver import CUSTOMER_POSTGRES, MANAGED_COLOCATED


def _headers(token: str, org_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}


def _seed(db_session):
    org = Organization(name="Setup Co", slug="setup-co", license_limit=5)
    db_session.add(org)
    db_session.flush()
    admin = User(email="setup-admin@test", full_name="Admin", hashed_password=hash_password("password"))
    db_session.add(admin)
    db_session.flush()
    db_session.add(OrganizationMembership(organization_id=org.id, user_id=admin.id, role=Role.ORG_ADMIN.value))
    db_session.commit()
    token = create_access_token(
        str(admin.id),
        {"organization_id": str(org.id), "role": Role.ORG_ADMIN.value, "aud": "aqrem-org-admin"},
    )
    return org, token


def test_postgres_step_unchecked_for_default_managed_row(db_session):
    org, _token = _seed(db_session)
    db_session.add(
        TenantDataStoreConfig(
            organization_id=org.id,
            storage_mode=MANAGED_COLOCATED,
            connection_method="managed",
            status="active",
            last_health_status="healthy",
            setup_validated_at=None,
        )
    )
    db_session.commit()
    data = build_setup_checklist(db_session, organization_id=org.id, control_db=db_session)
    by_id = {s["id"]: s for s in data["steps"]}
    assert by_id["postgres_database"]["status"] == "pending"


def test_postgres_step_complete_after_explicit_validation(db_session):
    from datetime import UTC, datetime

    org, _token = _seed(db_session)
    db_session.add(
        TenantDataStoreConfig(
            organization_id=org.id,
            storage_mode=MANAGED_COLOCATED,
            connection_method="managed",
            status="active",
            last_health_status="healthy",
            setup_validated_at=datetime.now(UTC),
        )
    )
    db_session.commit()
    data = build_setup_checklist(db_session, organization_id=org.id, control_db=db_session)
    by_id = {s["id"]: s for s in data["steps"]}
    assert by_id["postgres_database"]["status"] == "complete"
    assert data["total_count"] == 5


def test_org_admin_save_managed_marks_setup_complete(client: TestClient, db_session):
    org, token = _seed(db_session)
    res = client.put(
        "/api/v1/org-admin/data-storage",
        headers=_headers(token, str(org.id)),
        json={"storage_mode": "managed_colocated"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["setup_complete"] is True
    assert body["setup_validated_at"]

    overview = client.get("/api/v1/org-admin/overview", headers=_headers(token, str(org.id)))
    steps = {s["id"]: s for s in overview.json()["setup"]["steps"]}
    assert steps["postgres_database"]["status"] == "complete"


def test_customer_postgres_requires_healthy_preflight(db_session):
    org, _token = _seed(db_session)
    db_session.add(
        TenantDataStoreConfig(
            organization_id=org.id,
            storage_mode=CUSTOMER_POSTGRES,
            connection_method="public_internet",
            host="db.example.com",
            database_name="tenant",
            username="app",
            secret_reference="ref",
            status="active",
            last_health_status="failed",
        )
    )
    db_session.commit()
    data = build_setup_checklist(db_session, organization_id=org.id, control_db=db_session)
    by_id = {s["id"]: s for s in data["steps"]}
    assert by_id["postgres_database"]["status"] == "pending"

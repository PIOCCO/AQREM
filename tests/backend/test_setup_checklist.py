"""Setup checklist phase 2: PostgreSQL (org admin)."""

from __future__ import annotations

from app.core.roles import Role
from app.core.security import create_access_token, hash_password
from app.models.organization import Organization, OrganizationMembership, User
from app.models.tenant_data_store import TenantDataStoreConfig
from app.services.setup_checklist import build_setup_checklist
from app.tenant_store.resolver import CUSTOMER_POSTGRES, MANAGED_COLOCATED


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


def test_checklist_has_no_model_token_step(db_session):
    org, _token = _seed(db_session)
    db_session.add(
        TenantDataStoreConfig(
            organization_id=org.id,
            storage_mode=MANAGED_COLOCATED,
            connection_method="managed",
            status="active",
        )
    )
    db_session.commit()
    data = build_setup_checklist(db_session, organization_id=org.id, control_db=db_session)
    step_ids = [s["id"] for s in data["steps"]]
    assert "model_token" not in step_ids
    assert "postgres_database" in step_ids
    assert data["total_count"] == 5


def test_checklist_postgres_managed_complete(db_session):
    org, _token = _seed(db_session)
    db_session.add(
        TenantDataStoreConfig(
            organization_id=org.id,
            storage_mode=MANAGED_COLOCATED,
            connection_method="managed",
            status="active",
        )
    )
    db_session.commit()
    data = build_setup_checklist(db_session, organization_id=org.id, control_db=db_session)
    by_id = {s["id"]: s for s in data["steps"]}
    assert by_id["postgres_database"]["status"] == "complete"


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

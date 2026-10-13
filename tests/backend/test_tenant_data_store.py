"""Tenant data store resolver, SSRF, preflight, and isolation."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.roles import Role
from app.core.jwt_audiences import AUD_EMPLOYEE, AUD_ORG_ADMIN, AUD_PLATFORM
from app.core.security import create_access_token, hash_password
from app.models.organization import Organization, OrganizationMembership, User
from app.models.tenant_data_store import TenantDataStoreConfig
from app.tenant_store.exceptions import TenantHostRejected
from app.tenant_store.masking import mask_database_url
from app.tenant_store.resolver import CUSTOMER_POSTGRES, build_database_url, ensure_managed_config, open_tenant_session
from app.tenant_store.secrets import EnvSecretStore
from app.tenant_store.ssrf import validate_host_port


def test_ssrf_blocks_metadata_ip():
    with pytest.raises(TenantHostRejected):
        validate_host_port("169.254.169.254", 5432, allow_private=False)


def test_ssrf_blocks_localhost():
    with pytest.raises(TenantHostRejected):
        validate_host_port("127.0.0.1", 5432, allow_private=False)


def test_mask_database_url_hides_password():
    masked = mask_database_url("postgresql+psycopg://user:secret@db.example.com:5432/tenant")
    assert "secret" not in masked
    assert "db.example.com" in masked


def test_tenant_a_never_uses_tenant_b_engine(db_session: Session):
    org_a = Organization(name="A", slug=f"a-{uuid4().hex[:6]}")
    org_b = Organization(name="B", slug=f"b-{uuid4().hex[:6]}")
    db_session.add_all([org_a, org_b])
    db_session.flush()
    ensure_managed_config(db_session, org_a.id)
    cfg_b = TenantDataStoreConfig(
        organization_id=org_b.id,
        storage_mode=CUSTOMER_POSTGRES,
        connection_method="public_tls",
        host="203.0.113.10",
        port=5432,
        database_name="other",
        username="u",
        secret_reference="REF_B",
        ssl_mode="verify-full",
    )
    db_session.add(cfg_b)
    db_session.flush()
    secrets = EnvSecretStore()
    secrets.put("REF_B", "pw")
    url_b = build_database_url(cfg_b, secrets)
    url_a = build_database_url(ensure_managed_config(db_session, org_a.id), secrets)
    assert url_a != url_b


def test_open_tenant_session_managed_colocated(db_session: Session):
    org = Organization(name="Colo", slug=f"colo-{uuid4().hex[:6]}")
    db_session.add(org)
    db_session.flush()
    session = open_tenant_session(db_session, org.id)
    try:
        session.execute(__import__("sqlalchemy").text("SELECT 1"))
    finally:
        session.close()


def test_org_admin_storage_get_requires_admin(client: TestClient, db_session: Session):
    org = Organization(name="Store Co", slug=f"sc-{uuid4().hex[:6]}")
    user = User(email=f"admin-{uuid4().hex[:6]}@example.com", hashed_password=hash_password("x"), full_name="Admin")
    db_session.add_all([org, user])
    db_session.flush()
    db_session.add(
        OrganizationMembership(organization_id=org.id, user_id=user.id, role=Role.ORG_ADMIN.value),
    )
    db_session.commit()
    token = create_access_token(
        str(user.id),
        {"organization_id": str(org.id), "role": Role.ORG_ADMIN.value, "aud": "aqrem-org-admin"},
    )
    res = client.get(
        "/api/v1/org-admin/data-storage",
        headers={"Authorization": f"Bearer {token}", "X-Organization-Id": str(org.id)},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["storage_mode"] == "managed_colocated"
    assert "password" not in body

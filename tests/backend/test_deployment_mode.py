"""DEPLOYMENT_MODE=shared|dedicated behaviour."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.deployment import platform_route_allowed
from app.models.organization import Organization, OrganizationMembership


@pytest.fixture()
def dedicated(monkeypatch):
    monkeypatch.setenv("DEPLOYMENT_MODE", "dedicated")
    monkeypatch.setenv("DEDICATED_ORG_NAME", "Contoso Dedicated")
    monkeypatch.setenv("SETUP_TOKEN", "s3tup-token-for-tests")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_invalid_mode_rejected():
    with pytest.raises(Exception):
        Settings(deployment_mode="hybrid")


def test_shared_mode_unchanged(client: TestClient):
    r = client.get("/api/v1/setup/status")
    assert r.status_code == 200
    assert r.json() == {"deployment_mode": "shared", "setup_required": False, "organization_name": None,
                        "setup_token_configured": False, "license_state": None, "license_message": None}
    r = client.post("/api/v1/setup/first-admin", json={"setup_token": "x", "email": "a@b.co",
                                                        "full_name": "A", "password": "x" * 12})
    assert r.status_code == 404
    assert platform_route_allowed("/api/v1/admin/organizations", "POST", Settings())


def test_dedicated_first_admin_flow(dedicated, db_session):
    from app.main import create_app
    from app.db.session import get_db
    from app.tenant_store.deps import get_tenant_db

    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_tenant_db] = lambda: db_session
    with TestClient(app) as c:
        # db_session already may contain orgs from other tests in same tx: start clean view
        s = c.get("/api/v1/setup/status").json()
        assert s["deployment_mode"] == "dedicated"
        assert s["setup_token_configured"] is True
        org_count = db_session.query(Organization).filter(Organization.deleted_at.is_(None)).count()
        assert org_count == 1
        body = {"setup_token": "wrong", "email": "owner@contoso.example.com", "full_name": "Owner", "password": "a-very-long-pass"}
        assert c.post("/api/v1/setup/first-admin", json=body).status_code == 403
        body["setup_token"] = "s3tup-token-for-tests"
        r = c.post("/api/v1/setup/first-admin", json=body)
        assert r.status_code == 201, r.text
        assert r.json()["organization_name"] == "Contoso Dedicated"
        assert c.get("/api/v1/setup/status").json()["setup_required"] is False
        assert c.post("/api/v1/setup/first-admin", json=body).status_code == 409
        org = db_session.query(Organization).one()
        m = db_session.query(OrganizationMembership).filter_by(organization_id=org.id).one()
        assert m.role == "ORG_ADMIN"
        # platform console hidden
        assert c.get("/api/v1/admin/organizations").status_code == 404
        assert c.post("/api/v1/admin/organizations", json={}).status_code == 404
        assert c.get("/api/v1/master/environments").status_code == 404
    app.dependency_overrides.clear()


def test_dedicated_support_access_is_read_only():
    s = Settings(deployment_mode="dedicated", dedicated_support_access=True)
    assert platform_route_allowed("/api/v1/admin/organizations", "GET", s)
    assert not platform_route_allowed("/api/v1/admin/organizations", "POST", s)
    assert not platform_route_allowed("/api/v1/admin/organizations/x/delete", "POST", s)
    s2 = Settings(deployment_mode="dedicated")
    assert not platform_route_allowed("/api/v1/admin/organizations", "GET", s2)
    assert platform_route_allowed("/api/v1/org-admin/documents", "GET", s2)

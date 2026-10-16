"""Config externalisation, Key Vault loader, database 'test connection' checks."""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text

from app.core import keyvault
from app.core.config import Settings
from app.services.system.db_check import explain_connect_error, run_database_checks, safe_target
from tests.backend.conftest import DATABASE_URL

PROD = dict(app_env="production", secret_key="x" * 40, llm_provider="openai", openai_api_key="k")


def test_production_refuses_azurite():
    with pytest.raises(Exception, match="Azurite"):
        Settings(**PROD, azure_storage_connection_string="DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=x;BlobEndpoint=http://azurite:10000/devstoreaccount1")


def test_production_accepts_managed_identity_blob():
    s = Settings(**PROD, azure_storage_account_url="https://acct.privatelink.blob.core.windows.net")
    assert s.use_azure_blob_storage


def test_broker_url_override():
    assert Settings(redis_url="redis://a:6379/0").broker_url == "redis://a:6379/0"
    assert Settings(redis_url="redis://a", celery_broker_url="rediss://b:6380/0").broker_url == "rediss://b:6380/0"


class _FakeSecret:
    def __init__(self, value):
        self.value = value


class _FakeClient:
    def __init__(self, data):
        self.data = data

    def get_secret(self, name):
        if name not in self.data:
            exc = type("ResourceNotFoundError", (Exception,), {})()
            raise exc
        return _FakeSecret(self.data[name])


def test_key_vault_loader_fills_only_missing(monkeypatch):
    monkeypatch.setenv("KEY_VAULT_URL", "https://kv.vault.azure.net")
    monkeypatch.setenv("SECRET_KEY", "from-env")
    monkeypatch.delenv("SETUP_TOKEN", raising=False)
    monkeypatch.delenv("BREVO_API_KEY", raising=False)
    client = _FakeClient({"secret-key": "from-kv", "setup-token": "kv-setup"})
    report = keyvault.load_key_vault_secrets(client=client, force=True)
    assert os.environ["SECRET_KEY"] == "from-env"
    assert os.environ["SETUP_TOKEN"] == "kv-setup"
    assert "SETUP_TOKEN" in report["loaded"] and "SECRET_KEY" in report["skipped_env"]
    assert "BREVO_API_KEY" in report["missing"]
    monkeypatch.delenv("SETUP_TOKEN", raising=False)


def test_safe_target_hides_password():
    t = safe_target("postgresql+psycopg://u:SuperSecret@db.internal:5433/aqrem")
    assert "SuperSecret" not in t and "db.internal:5433/aqrem" in t


def test_connect_error_messages():
    assert "password" in explain_connect_error(Exception('FATAL: password authentication failed for user "x"'))
    assert "DNS" in explain_connect_error(Exception("could not translate host name"))
    assert "TLS" in explain_connect_error(Exception("no pg_hba.conf entry for host, SSL off"))


def test_db_check_against_test_database(engine):
    r = run_database_checks(DATABASE_URL, role="app", engine=engine)
    names = {c.name: c for c in r.checks}
    assert names["connection"].status == "ok"
    assert names["version"].status == "ok"
    assert names["vector_extension"].status == "ok"
    assert names["tls"].status in {"ok", "warn"}
    # The test role is a superuser -> least-privilege warning, not a failure.
    assert names["least_privilege"].status == "warn"
    assert r.ok


def test_db_check_unreachable_host():
    r = run_database_checks("postgresql+psycopg://u:p@127.0.0.1:1/x", role="app")
    assert not r.ok
    assert r.checks[0].name == "connection" and r.checks[0].status == "fail"
    assert "p@" not in str(r.to_dict())


def test_db_check_tls_required_fails_without_tls(engine):
    url = DATABASE_URL + ("&" if "?" in DATABASE_URL else "?") + "sslmode=disable"
    r = run_database_checks(url, role="app", require_tls=True)
    tls = next(c for c in r.checks if c.name == "tls")
    assert tls.status == "fail" and "sslmode" in tls.message


def test_db_check_restricted_role_reports_missing_privileges(engine):
    role = f"aq_ro_{uuid.uuid4().hex[:8]}"
    with engine.begin() as conn:
        conn.execute(text(f"CREATE ROLE {role} LOGIN PASSWORD 'pw-test-123'"))
        conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {role}"))
        conn.execute(text(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {role}"))
    try:
        from sqlalchemy.engine import make_url

        url = make_url(DATABASE_URL).set(username=role, password="pw-test-123")
        r = run_database_checks(url.render_as_string(hide_password=False), role="app")
        perms = next(c for c in r.checks if c.name == "permissions")
        assert perms.status == "fail" and "INSERT" in perms.message
        lp = next(c for c in r.checks if c.name == "least_privilege")
        assert lp.status == "ok"
    finally:
        with engine.begin() as conn:
            conn.execute(text(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {role}"))
            conn.execute(text(f"REVOKE ALL ON SCHEMA public FROM {role}"))
            conn.execute(text(f"DROP ROLE {role}"))


def test_health_and_version_endpoints(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert set(body["dependencies"]) >= {"database", "broker", "storage", "llm", "license"}
    assert body["dependencies"]["database"]["status"] in {"ok", "degraded"}
    assert "aqrem:aqrem" not in r.text
    v = client.get("/api/v1/version").json()
    assert v["deployment_mode"] == "shared" and v["version"]

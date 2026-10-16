"""Redaction filter, JSON logs, diagnostics bundle (no secrets / no content)."""

from __future__ import annotations

import io
import json
import logging
import zipfile
from uuid import uuid4

from app.core.config import get_settings
from app.core.logging_setup import JsonFormatter, RedactionFilter, recent_errors, redact_text

SECRETS = [
    "postgresql+psycopg://aqrem_app:Sup3rS3cret!@db.internal:5432/aqrem",
    "DefaultEndpointsProtocol=https;AccountName=acct;AccountKey=abcDEF123456789==;EndpointSuffix=core.windows.net",
    "https://acct.blob.core.windows.net/c/x?sv=2024&sig=AbCdEf123%2B%3D",
    "Authorization: Bearer abcdefghijklmnop.qrstuvwxyz",
    "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U",
    "api_key=sk-live-1234567890abcdef",
    "password: hunter2hunter2",
]


def test_redact_text_patterns():
    for s in SECRETS:
        red = redact_text(s)
        for needle in ("Sup3rS3cret", "abcDEF123456789", "AbCdEf123", "abcdefghijklmnop", "dozjgNryP4J3",
                       "sk-live-1234567890abcdef", "hunter2hunter2"):
            assert needle not in red, (s, red)
    assert "db.internal:5432" in redact_text(SECRETS[0])


def _record(msg, *args, **extra):
    rec = logging.LogRecord("aqrem.test", logging.WARNING, __file__, 1, msg, args, None)
    for k, v in extra.items():
        setattr(rec, k, v)
    return rec


def test_filter_redacts_message_args_and_content_extras():
    rec = _record("connect %s failed", SECRETS[0], content="Confidential salary table 120000",
                  question="what is the CEO salary?", organization_id="o1")
    RedactionFilter().filter(rec)
    out = JsonFormatter().format(rec)
    data = json.loads(out)
    assert "Sup3rS3cret" not in out and "120000" not in out and "CEO salary" not in out
    assert data["content"].startswith("[redacted len=") and data["organization_id"] == "o1"
    assert data["level"] == "WARNING" and data["logger"] == "aqrem.test"


def test_production_forces_debug_rag_off():
    from app.core.config import Settings

    s = Settings(app_env="production", secret_key="x" * 40, llm_provider="openai", openai_api_key="k",
                 azure_storage_account_url="https://a.blob.core.windows.net", debug_rag=True)
    assert s.debug_rag is False


def test_diagnostics_bundle_has_no_secrets_or_content(client, db_session, monkeypatch):
    from app.core.jwt_audiences import AUD_PLATFORM
    from app.core.security import create_access_token, hash_password
    from app.models.organization import User

    monkeypatch.setenv("SETUP_TOKEN", "very-secret-setup-token-xyz")
    get_settings.cache_clear()
    logging.getLogger("aqrem.test").error("upload failed for %s", SECRETS[1])
    recent_errors.emit(_record("db %s", SECRETS[0]))
    admin = User(email=f"sa-{uuid4().hex[:6]}@example.com", full_name="SA", hashed_password=hash_password("x"),
                 is_platform_admin=True, platform_role="SUPER_ADMIN", is_active=True)
    db_session.add(admin)
    db_session.commit()
    tok = create_access_token(str(admin.id), {"platform_role": "SUPER_ADMIN"}, audience=AUD_PLATFORM)
    r = client.get("/api/v1/admin/system/diagnostics", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200, r.text[:300]
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    body = zf.read("diagnostics.json").decode()
    data = json.loads(body)
    for needle in ("very-secret-setup-token-xyz", "aqrem:aqrem@", "Sup3rS3cret", "abcDEF123456789"):
        assert needle not in body, needle
    assert data["config_present"]["setup_token"] is True
    assert "dependencies" in data and "database_check" in data
    get_settings.cache_clear()


def test_org_admin_diagnostics_only_in_dedicated(client):
    r = client.get("/api/v1/org-admin/system/diagnostics")
    assert r.status_code == 404

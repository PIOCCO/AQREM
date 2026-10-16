"""CHECK 3: dedicated /setup hardening (one-time + expiring token, 404 after setup, network gate,
rate limit/lockout, no token in logs, re-open only via the operator CLI)."""

from __future__ import annotations

import contextlib
import logging
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.logging_setup import RedactionFilter, redact_text
from app.models.organization import OrganizationMembership
from app.models.setup_token import SetupAttempt, SetupToken
from app.services import setup_guard

TOKEN = "bootstrap-setup-token-for-tests-0123456789"
PRIVATE = ("10.20.30.40", 50000)


@pytest.fixture()
def dedicated_env(monkeypatch):
    monkeypatch.setenv("DEPLOYMENT_MODE", "dedicated")
    monkeypatch.setenv("DEDICATED_ORG_NAME", "Contoso Dedicated")
    monkeypatch.setenv("SETUP_TOKEN", TOKEN)
    monkeypatch.setenv("SETUP_MAX_ATTEMPTS_PER_IP", "3")
    monkeypatch.setenv("SETUP_MAX_ATTEMPTS_GLOBAL", "5")
    get_settings.cache_clear()
    yield monkeypatch
    get_settings.cache_clear()


@pytest.fixture()
def make_client(dedicated_env, db_session):
    from app.db.session import get_db
    from app.main import create_app
    from app.tenant_store.deps import get_tenant_db

    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_tenant_db] = lambda: db_session
    stack = contextlib.ExitStack()

    def _make(peer=PRIVATE):
        return stack.enter_context(TestClient(app, client=peer))

    yield _make
    stack.close()
    app.dependency_overrides.clear()


def _body(token=TOKEN, email="owner@contoso.example.com"):
    return {"setup_token": token, "email": email, "full_name": "Owner", "password": "a-very-long-pass"}


def _admins(db):
    return db.query(OrganizationMembership).filter_by(role="ORG_ADMIN").count()


@contextlib.contextmanager
def _session_cm(db):
    yield db


def _cli(monkeypatch, db, argv, stdin=None):
    import io
    import sys

    import app.db.session as session_mod
    from app.setup.__main__ import main

    monkeypatch.setattr(session_mod, "SessionLocal", lambda: _session_cm(db))
    if stdin is not None:
        monkeypatch.setattr(sys, "stdin", io.StringIO(stdin + "\n"))
    return main(argv)


# ---------------------------------------------------------------- one-time token, storage


def test_token_stored_only_as_hash_and_works_once(make_client, db_session):
    c = make_client()
    s = c.get("/api/v1/setup/status")
    assert s.status_code == 200, s.text
    assert s.json()["setup_required"] is True and s.json()["expires_at"]
    rows = db_session.query(SetupToken).all()
    assert len(rows) == 1 and rows[0].token_hash == setup_guard.hash_token(TOKEN)
    assert TOKEN not in repr(vars(rows[0]))

    assert c.post("/api/v1/setup/first-admin", json=_body()).status_code == 201
    db_session.refresh(rows[0])
    assert rows[0].consumed_at is not None
    # second use: setup is closed -> 404 exactly like an unknown route
    r = c.post("/api/v1/setup/first-admin", json=_body(email="second@contoso.example.com"))
    assert r.status_code == 404
    assert r.json() == c.get("/api/v1/definitely-not-a-route").json()
    assert _admins(db_session) == 1


def test_wrong_token_rejected(make_client, db_session):
    c = make_client()
    r = c.post("/api/v1/setup/first-admin", json=_body(token="nope-nope-nope"))
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "SETUP_TOKEN_INVALID"
    assert _admins(db_session) == 0
    assert db_session.query(SetupAttempt).filter_by(success=False).count() == 1


def test_expired_token(make_client, db_session):
    c = make_client()
    assert c.get("/api/v1/setup/status").status_code == 200
    row = db_session.query(SetupToken).one()
    row.issued_at = datetime.now(UTC) - timedelta(minutes=61)
    db_session.flush()
    for r in (c.get("/api/v1/setup/status"), c.post("/api/v1/setup/first-admin", json=_body())):
        assert r.status_code == 410
        assert r.json()["detail"]["code"] == "SETUP_TOKEN_EXPIRED"
    assert _admins(db_session) == 0


def test_ttl_is_configurable(dedicated_env, make_client, db_session):
    dedicated_env.setenv("SETUP_TOKEN_TTL_MINUTES", "5")
    get_settings.cache_clear()
    c = make_client()
    assert c.get("/api/v1/setup/status").status_code == 200
    row = db_session.query(SetupToken).one()
    row.issued_at = datetime.now(UTC) - timedelta(minutes=6)
    db_session.flush()
    assert c.get("/api/v1/setup/status").status_code == 410


# ---------------------------------------------------------------- rate limit


def test_per_ip_lockout_then_other_ip_still_allowed(make_client, db_session):
    c = make_client()
    for _ in range(3):
        assert c.post("/api/v1/setup/first-admin", json=_body(token="wrong-token-xx")).status_code == 403
    r = c.post("/api/v1/setup/first-admin", json=_body())  # even the right token is refused while locked
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) > 0
    assert r.json()["detail"]["code"] == "SETUP_LOCKED"
    assert c.get("/api/v1/setup/status").status_code == 429
    assert _admins(db_session) == 0
    other = make_client(("10.20.30.41", 50001))
    assert other.post("/api/v1/setup/first-admin", json=_body()).status_code == 201


def test_global_lockout_across_ips(make_client, db_session):
    for i in range(5):
        c = make_client((f"10.0.0.{i + 1}", 40000 + i))
        assert c.post("/api/v1/setup/first-admin", json=_body(token="wrong-token-xx")).status_code == 403
    fresh = make_client(("10.0.9.9", 49999))
    assert fresh.post("/api/v1/setup/first-admin", json=_body()).status_code == 429


def test_lockout_expires(make_client, db_session):
    c = make_client()
    for _ in range(3):
        c.post("/api/v1/setup/first-admin", json=_body(token="wrong-token-xx"))
    for a in db_session.query(SetupAttempt).all():
        a.attempted_at = datetime.now(UTC) - timedelta(minutes=16)
    db_session.flush()
    assert c.post("/api/v1/setup/first-admin", json=_body()).status_code == 201


# ---------------------------------------------------------------- network gate


def test_public_client_gets_404(make_client, db_session):
    c = make_client(("203.0.113.7", 50000))
    assert c.get("/api/v1/setup/status").status_code == 404
    assert c.post("/api/v1/setup/first-admin", json=_body()).status_code == 404
    assert _admins(db_session) == 0
    assert db_session.query(SetupAttempt).count() == 0  # blocked before any token handling


def test_forwarded_for_without_declared_proxy_fails_closed(make_client):
    c = make_client()
    assert c.get("/api/v1/setup/status", headers={"X-Forwarded-For": "10.0.0.1"}).status_code == 404


def test_trusted_proxy_hops_and_spoofing(dedicated_env, make_client):
    dedicated_env.setenv("SETUP_TRUSTED_PROXY_HOPS", "2")
    get_settings.cache_clear()
    c = make_client(("10.0.0.4", 50000))  # web nginx; Azure ingress appended 10.0.0.9
    assert c.get("/api/v1/setup/status", headers={"X-Forwarded-For": "203.0.113.5, 10.0.0.9"}).status_code == 404
    # attacker prepends a private address: still resolves to the real public client
    spoof = {"X-Forwarded-For": "10.1.1.1, 203.0.113.5, 10.0.0.9"}
    assert c.get("/api/v1/setup/status", headers=spoof).status_code == 404
    assert c.get("/api/v1/setup/status", headers={"X-Forwarded-For": "192.168.1.20, 10.0.0.9"}).status_code == 200
    dedicated_env.setenv("SETUP_ALLOWED_CIDRS", "203.0.113.5/32")
    get_settings.cache_clear()
    assert c.get("/api/v1/setup/status", headers=spoof).status_code == 200


def test_shared_mode_has_no_setup(client: TestClient):
    assert client.get("/api/v1/setup/status").status_code == 404
    assert client.post("/api/v1/setup/first-admin", json=_body()).status_code == 404


# ---------------------------------------------------------------- after setup, re-activation


def test_after_setup_page_and_api_404_and_env_cannot_reopen(dedicated_env, make_client, db_session):
    c = make_client()
    assert c.post("/api/v1/setup/first-admin", json=_body()).status_code == 201
    assert c.get("/api/v1/setup/status").status_code == 404
    # operator changes SETUP_TOKEN in the environment: still closed
    dedicated_env.setenv("SETUP_TOKEN", "a-brand-new-env-token-0123456789")
    get_settings.cache_clear()
    assert c.get("/api/v1/setup/status").status_code == 404
    r = c.post("/api/v1/setup/first-admin", json=_body(token="a-brand-new-env-token-0123456789", email="x@contoso.example.com"))
    assert r.status_code == 404
    # deployment mode still discoverable for the UI
    assert c.get("/api/v1/version").json()["deployment_mode"] == "dedicated"


def test_existing_environment_without_token_rows_stays_closed(make_client, db_session):
    """Upgrading an env whose admin already exists must not mint a bootstrap token."""
    c = make_client()
    assert c.post("/api/v1/setup/first-admin", json=_body()).status_code == 201
    db_session.query(SetupToken).delete()
    db_session.flush()
    assert c.get("/api/v1/setup/status").status_code == 404
    assert db_session.query(SetupToken).count() == 0


def test_reactivation_only_via_operator_cli(dedicated_env, make_client, db_session, capsys):
    c = make_client()
    assert c.post("/api/v1/setup/first-admin", json=_body()).status_code == 201
    assert c.get("/api/v1/setup/status").status_code == 404

    assert _cli(dedicated_env, db_session, ["reset"]) == 2  # --confirm required
    assert c.get("/api/v1/setup/status").status_code == 404
    # the old (consumed) token can't be re-issued
    assert _cli(dedicated_env, db_session, ["reset", "--confirm", "--token-stdin"], stdin=TOKEN) == 2
    capsys.readouterr()

    assert _cli(dedicated_env, db_session, ["reset", "--confirm"]) == 0
    new_token = capsys.readouterr().out.strip().splitlines()[-1]
    assert len(new_token) >= 24 and new_token != TOKEN
    assert c.get("/api/v1/setup/status").status_code == 200
    assert c.post("/api/v1/setup/first-admin", json=_body(token=TOKEN, email="r@contoso.example.com")).status_code == 403
    assert c.post("/api/v1/setup/first-admin", json=_body(token=new_token, email="r@contoso.example.com")).status_code == 201
    assert _admins(db_session) == 2
    assert c.get("/api/v1/setup/status").status_code == 404
    assert c.post("/api/v1/setup/first-admin", json=_body(token=new_token, email="z@contoso.example.com")).status_code == 404

    assert _cli(dedicated_env, db_session, ["status"]) == 0
    assert new_token not in capsys.readouterr().out


def test_cli_reset_revokes_unused_token(dedicated_env, make_client, db_session, capsys):
    c = make_client()
    assert c.get("/api/v1/setup/status").status_code == 200
    assert _cli(dedicated_env, db_session, ["reset", "--confirm", "--token-stdin"],
                stdin="operator-chosen-token-abcdefghijklmnop") == 0
    assert "operator-chosen-token" not in capsys.readouterr().out  # stdin token is not echoed
    assert c.post("/api/v1/setup/first-admin", json=_body()).status_code == 403  # bootstrap revoked
    assert c.post("/api/v1/setup/first-admin",
                  json=_body(token="operator-chosen-token-abcdefghijklmnop")).status_code == 201


# ---------------------------------------------------------------- logging


def test_token_never_appears_in_logs(make_client, db_session, caplog):
    caplog.set_level(logging.DEBUG)
    c = make_client()
    c.get("/api/v1/setup/status")
    c.post("/api/v1/setup/first-admin", json=_body(token="wrong-" + TOKEN))
    c.post("/api/v1/setup/first-admin", json=_body())
    c.post("/api/v1/setup/first-admin", json=_body())
    raw = "\n".join(f"{r.getMessage()} {vars(r)}" for r in caplog.records)
    assert TOKEN not in raw

    # Defence in depth: if anything (e.g. an access log or a library) does log it, it is redacted.
    flt = RedactionFilter()
    rec = logging.makeLogRecord({"msg": 'POST /api/v1/setup/first-admin?setup_token=%s body={"setup_token": "%s"} %s',
                                 "args": (TOKEN, TOKEN, TOKEN), "name": "uvicorn.access"})
    flt.filter(rec)
    assert TOKEN not in rec.getMessage()
    assert TOKEN not in redact_text(f"stray {TOKEN} value")
    rec2 = logging.makeLogRecord({"msg": "x", "setup_token": TOKEN})
    flt.filter(rec2)
    assert rec2.setup_token == "***"

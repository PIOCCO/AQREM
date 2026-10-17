"""Operator recovery CLI (python -m app.ops) and the image/schema compatibility guard."""

from __future__ import annotations

import ast
import contextlib
import pathlib

import pytest
from fastapi.routing import APIRoute
from sqlalchemy import text

from app.core.security import verify_password
from app.db import migrate
from app.models.audit import AuditEvent
from app.models.organization import Organization, OrganizationMembership, User

APP_DIR = pathlib.Path(migrate.__file__).resolve().parents[1]


@contextlib.contextmanager
def _cm(db):
    yield db


def _ops(monkeypatch, db, argv):
    import app.db.session as session_mod
    from app.ops.__main__ import main

    monkeypatch.setattr(session_mod, "SessionLocal", lambda: _cm(db))
    return main(argv)


def _org(db, slug="acme-ops"):
    org = Organization(name="Acme Ops", slug=slug)
    db.add(org)
    db.flush()
    return org


# ---------------------------------------------------------------- recover-admin


def test_recover_admin_existing_user_with_password_reset(monkeypatch, db_session, capsys):
    org = _org(db_session)
    u = User(email="lost@acme.example", hashed_password="x", full_name="Lost")
    db_session.add(u)
    db_session.flush()
    db_session.add(OrganizationMembership(organization_id=org.id, user_id=u.id, role="VIEWER"))
    db_session.flush()
    assert _ops(monkeypatch, db_session, ["recover-admin", "--org", "acme-ops", "--email", "LOST@acme.example",
                                          "--reset-password"]) == 0
    out = capsys.readouterr()
    temp = out.out.strip().splitlines()[-1]
    assert len(temp) >= 16 and temp not in out.err  # printed once, on stdout only
    db_session.refresh(u)
    assert verify_password(temp, u.hashed_password) and u.must_change_password is True
    m = db_session.query(OrganizationMembership).filter_by(organization_id=org.id, user_id=u.id).one()
    assert m.role == "ORG_ADMIN"
    ev = db_session.query(AuditEvent).filter_by(action="admin_recovered_by_operator").one()
    assert ev.organization_id == org.id
    meta = ev.metadata_json if hasattr(ev, "metadata_json") else ev.event_metadata
    assert temp not in str(meta) and meta["previous_role"] == "VIEWER" and meta["password_reset"] is True


def test_recover_admin_without_reset_does_not_touch_password(monkeypatch, db_session, capsys):
    org = _org(db_session, "acme-ops2")
    u = User(email="keep@acme.example", hashed_password="unchanged-hash", full_name="Keep")
    db_session.add(u)
    db_session.flush()
    assert _ops(monkeypatch, db_session, ["recover-admin", "--org", org.slug, "--email", u.email]) == 0
    assert capsys.readouterr().out == ""
    db_session.refresh(u)
    assert u.hashed_password == "unchanged-hash"


def test_recover_admin_new_user_gets_temp_password_and_unknown_org_refused(monkeypatch, db_session, capsys):
    _org(db_session, "acme-ops3")
    assert _ops(monkeypatch, db_session, ["recover-admin", "--org", "nope", "--email", "a@b.example"]) == 2
    assert _ops(monkeypatch, db_session, ["recover-admin", "--org", "acme-ops3", "--email", "new@acme.example"]) == 0
    temp = capsys.readouterr().out.strip().splitlines()[-1]
    u = db_session.query(User).filter_by(email="new@acme.example").one()
    assert verify_password(temp, u.hashed_password) and u.must_change_password


def _walk_endpoints(app):
    found = []

    def walk(routes):
        for r in routes:
            if isinstance(r, APIRoute):
                found.append((r.path, r.endpoint))
            elif type(r).__name__ == "_IncludedRouter":
                ctx = r.effective_route_contexts
                for x in (ctx() if callable(ctx) else ctx):
                    if type(x).__name__ == "_IncludedRouter":
                        walk([x])
                    else:
                        found.append((x.path, getattr(x, "endpoint", None)))
            elif hasattr(r, "path"):
                found.append((r.path, getattr(r, "endpoint", None)))
    walk(app.routes)
    return found


def test_no_web_route_exposes_operator_clis():
    from app.main import create_app

    routes = _walk_endpoints(create_app())
    assert len(routes) > 100
    for path, endpoint in routes:
        assert "recover" not in path.lower() and "clear-lockout" not in path.lower(), path
        mod = getattr(endpoint, "__module__", "") or ""
        assert not mod.startswith(("app.ops", "app.setup")), (path, mod)
    # and no web-facing module imports them
    for f in (APP_DIR / "api").rglob("*.py"):
        tree = ast.parse(f.read_text())
        for node in ast.walk(tree):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else (
                [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
            for n in names:
                assert not n.startswith(("app.ops", "app.setup")), f"{f} imports {n}"


# ---------------------------------------------------------------- schema guard


@pytest.fixture()
def guard_conn(engine):
    conn = engine.connect()
    trans = conn.begin()
    migrate._m6_schema_guard(conn)
    conn.execute(text(f"DELETE FROM {migrate.GUARD_TABLE}"))
    yield conn
    trans.rollback()
    conn.close()


def _set(conn, **kv):
    for k, v in kv.items():
        conn.execute(text(f"INSERT INTO {migrate.GUARD_TABLE} (key, value) VALUES (:k, :v) "
                          "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"), {"k": k, "v": v})


def test_guard_accepts_current_image(guard_conn):
    migrate._write_guard(guard_conn, {m.version for m in migrate.MIGRATIONS})
    g = migrate.read_guard(guard_conn)
    assert g == {"min_image_schema": "5", "required_features": "rls_org_isolation,setup_tokens_v1"}
    migrate.check_image_compatible(guard_conn)


def test_guard_refuses_older_image(guard_conn):
    _set(guard_conn, min_image_schema=str(migrate.LATEST_VERSION + 1), required_features="rls_org_isolation")
    with pytest.raises(migrate.ImageTooOldError, match="older than the database requires"):
        migrate.check_image_compatible(guard_conn)


def test_guard_refuses_unknown_required_feature(guard_conn):
    _set(guard_conn, min_image_schema="1", required_features="rls_org_isolation,feature_from_the_future")
    with pytest.raises(migrate.ImageTooOldError, match="feature_from_the_future"):
        migrate.check_image_compatible(guard_conn)


def test_guard_unreadable_marker_fails_closed(guard_conn):
    _set(guard_conn, min_image_schema="garbage")
    with pytest.raises(migrate.ImageTooOldError):
        migrate.check_image_compatible(guard_conn)


def test_guard_is_never_lowered(guard_conn):
    _set(guard_conn, min_image_schema="5", required_features="rls_org_isolation,setup_tokens_v1")
    migrate._write_guard(guard_conn, {1, 2})  # e.g. a partial view must not lower the marker
    assert migrate.read_guard(guard_conn)["min_image_schema"] == "5"
    assert "setup_tokens_v1" in migrate.read_guard(guard_conn)["required_features"]


def test_no_marker_table_means_compatible(engine):
    with engine.connect() as conn:
        trans = conn.begin()
        conn.execute(text(f"DROP TABLE IF EXISTS {migrate.GUARD_TABLE}"))  # noqa: test-only, rolled back
        migrate.check_image_compatible(conn)
        trans.rollback()


def test_migrator_refuses_newer_database(guard_conn, monkeypatch):
    _set(guard_conn, min_image_schema="999")

    class _Eng:
        @contextlib.contextmanager
        def begin(self):
            yield guard_conn

    with pytest.raises(migrate.ImageTooOldError):
        migrate.run_migrations(_Eng())


def test_app_startup_refuses_when_image_too_old(monkeypatch):
    from fastapi.testclient import TestClient

    import app.db.migrate as m
    from app.main import create_app

    def boom(_conn):
        raise m.ImageTooOldError("This image (schema 6) is older than the database requires")

    monkeypatch.setattr(m, "check_image_compatible", boom)
    with pytest.raises(m.ImageTooOldError):
        with TestClient(create_app()):
            pass


def test_flagged_migrations():
    flagged = {m.version: m.requires_image_feature for m in migrate.MIGRATIONS if m.requires_image_feature}
    assert flagged == {3: "rls_org_isolation", 5: "setup_tokens_v1"}

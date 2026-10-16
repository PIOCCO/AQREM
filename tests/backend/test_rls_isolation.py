"""Database-level isolation (PostgreSQL RLS), tested by connecting DIRECTLY as non-superuser roles.

These tests bypass application filtering entirely: every query below deliberately omits any
``WHERE organization_id = ...`` so only the RLS policies can be protecting the data.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.db.rls import ALL_RLS_TABLES, CONTROL_GROUP, apply_rls, scope_session_to_org

import os

DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql+psycopg://aqrem:aqrem@localhost:5432/aqrem_test")

APP_ROLE = "aqrem_rls_t_tenant"   # data plane: not in aqrem_rls_control
CTL_ROLE = "aqrem_rls_t_control"  # control plane: member of aqrem_rls_control
PW = "rls-test-" + uuid.uuid4().hex
from app.models.evidence import EMBEDDING_DIM as DIM  # noqa: E402


def _vec(hot: int) -> str:
    v = [0.0] * DIM
    v[hot] = 1.0
    return "[" + ",".join(str(x) for x in v) + "]"


def _url_for(role: str) -> str:
    return make_url(DATABASE_URL).set(username=role, password=PW).render_as_string(hide_password=False)


@pytest.fixture(scope="module")
def rls_db(engine):
    with engine.begin() as conn:
        apply_rls(conn)
        for role in (APP_ROLE, CTL_ROLE):
            conn.execute(text(f"DROP OWNED BY {role}") if conn.execute(
                text("SELECT 1 FROM pg_roles WHERE rolname=:r"), {"r": role}).scalar() else text("SELECT 1"))
            conn.execute(text(f"DROP ROLE IF EXISTS {role}"))
            conn.execute(text(f"CREATE ROLE {role} LOGIN NOBYPASSRLS PASSWORD '{PW}'"))
            conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {role}"))
            conn.execute(text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}"))
        conn.execute(text(f"GRANT {CONTROL_GROUP} TO {CTL_ROLE}"))
        orgs = {}
        for key, hot in (("a", 0), ("b", 1)):
            org_id, user_id, src_id, ev_id = (uuid.uuid4() for _ in range(4))
            conn.execute(text(
                "INSERT INTO organizations (id, name, slug, is_active, license_limit, license_status, chat_shares_enabled, "
                "chat_share_ttl_days) VALUES (:i, :n, :s, true, 0, 'active', false, 7)"
            ), {"i": org_id, "n": f"RLS Org {key}", "s": f"rls-{key}-{org_id.hex[:8]}"})
            conn.execute(text(
                "INSERT INTO users (id, email, full_name, hashed_password, is_active, is_platform_admin, "
                "platform_auth_version, must_change_password) VALUES (:i, :e, :n, 'x', true, false, 1, false)"
            ), {"i": user_id, "e": f"rls-{key}-{org_id.hex[:8]}@example.com", "n": key})
            conn.execute(text(
                "INSERT INTO organization_memberships (id, organization_id, user_id, role, is_active, auth_version) "
                "VALUES (:i, :o, :u, 'org_admin', true, 1)"
            ), {"i": uuid.uuid4(), "o": org_id, "u": user_id})
            conn.execute(text(
                "INSERT INTO sources (id, organization_id, name, source_type, scope, status, config, visibility_mode) "
                "VALUES (:i, :o, :n, 'upload', 'organization', 'ready', '{}', 'all_members')"
            ), {"i": src_id, "o": org_id, "n": f"src-{key}"})
            conn.execute(text(
                "INSERT INTO evidence_items (id, organization_id, source_id, source_type, scope, file_name, "
                "file_path, content, content_type, chunk_index, content_hash, metadata, visibility_mode, embedding) "
                "VALUES (:i, :o, :s, 'upload', 'organization', 'f.txt', 'f.txt', :c, 'text/plain', 0, 'h', '{}', "
                "'all_members', CAST(:e AS vector))"
            ), {"i": ev_id, "o": org_id, "s": src_id, "c": f"secret of org {key}", "e": _vec(hot)})
            conn.execute(text(
                "INSERT INTO audit_events (id, organization_id, action, resource_type, metadata) "
                "VALUES (:i, :o, 'rls_test', 'test', '{}')"
            ), {"i": uuid.uuid4(), "o": org_id})
            orgs[key] = {"org": org_id, "user": user_id, "source": src_id, "evidence": ev_id}
    app_eng = create_engine(_url_for(APP_ROLE))
    ctl_eng = create_engine(_url_for(CTL_ROLE))
    yield {"orgs": orgs, "app": app_eng, "ctl": ctl_eng}
    app_eng.dispose()
    ctl_eng.dispose()
    with engine.begin() as conn:
        for o in orgs.values():
            conn.execute(text("DELETE FROM audit_events WHERE organization_id = :o"), {"o": o["org"]})
            conn.execute(text("DELETE FROM evidence_items WHERE organization_id = :o"), {"o": o["org"]})
            conn.execute(text("DELETE FROM sources WHERE organization_id = :o"), {"o": o["org"]})
            conn.execute(text("DELETE FROM organization_memberships WHERE organization_id = :o"), {"o": o["org"]})
            conn.execute(text("DELETE FROM users WHERE id = :u"), {"u": o["user"]})
            conn.execute(text("DELETE FROM organizations WHERE id = :o"), {"o": o["org"]})
        for role in (APP_ROLE, CTL_ROLE):
            conn.execute(text(f"DROP OWNED BY {role}"))
            conn.execute(text(f"DROP ROLE {role}"))
        # Leave the shared test schema as other tests expect (they run as superuser anyway).
        for t, pol in conn.execute(text(
                "SELECT tablename, policyname FROM pg_policies WHERE schemaname='public'")).all():
            conn.execute(text(f'DROP POLICY "{pol}" ON "{t}"'))
        for t in ALL_RLS_TABLES:
            conn.execute(text(f"ALTER TABLE IF EXISTS {t} NO FORCE ROW LEVEL SECURITY"))
            conn.execute(text(f"ALTER TABLE IF EXISTS {t} DISABLE ROW LEVEL SECURITY"))


def _as(conn, org):
    conn.execute(text("SELECT set_config('app.current_org', :o, true)"), {"o": str(org) if org else ""})


def test_roles_are_not_bypassrls_or_superuser(rls_db):
    with rls_db["app"].connect() as c:
        row = c.execute(text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")).one()
        assert row == (False, False)
        owners = c.execute(text(
            "SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tableowner = current_user")).scalar()
        assert owners == 0


def test_all_client_tables_have_forced_rls(rls_db):
    with rls_db["app"].connect() as c:
        rows = dict(c.execute(text(
            "SELECT relname, relrowsecurity AND relforcerowsecurity FROM pg_class "
            "WHERE relname = ANY(:t) AND relkind = 'r'"), {"t": list(ALL_RLS_TABLES)}).all())
    missing = [t for t in ALL_RLS_TABLES if not rows.get(t)]
    assert not missing, missing


@pytest.mark.parametrize("engine_key", ["app", "ctl"])
def test_unset_org_sees_no_tenant_rows(rls_db, engine_key):
    with rls_db[engine_key].begin() as c:
        for t in ("evidence_items", "sources", "audit_events"):
            assert c.execute(text(f"SELECT count(*) FROM {t}")).scalar() == 0, t
        _as(c, "")  # empty string also fails closed
        assert c.execute(text("SELECT count(*) FROM evidence_items")).scalar() == 0


@pytest.mark.parametrize("engine_key", ["app", "ctl"])
def test_select_and_vector_search_only_own_org(rls_db, engine_key):
    a, b = rls_db["orgs"]["a"], rls_db["orgs"]["b"]
    with rls_db[engine_key].begin() as c:
        _as(c, a["org"])
        ids = {r[0] for r in c.execute(text("SELECT id FROM evidence_items"))}
        assert ids == {a["evidence"]}
        # pgvector similarity query aimed exactly at org B's embedding, no org filter at all.
        rows = c.execute(text(
            "SELECT id, content FROM evidence_items ORDER BY embedding <=> CAST(:q AS vector) LIMIT 10"
        ), {"q": _vec(1)}).all()
        assert [r[0] for r in rows] == [a["evidence"]]
        assert all("org b" not in r[1] for r in rows)
        assert c.execute(text("SELECT count(*) FROM evidence_items WHERE id = :i"), {"i": b["evidence"]}).scalar() == 0


@pytest.mark.parametrize("engine_key", ["app", "ctl"])
def test_update_delete_other_org_affect_nothing(rls_db, engine_key):
    a, b = rls_db["orgs"]["a"], rls_db["orgs"]["b"]
    with rls_db[engine_key].begin() as c:
        _as(c, a["org"])
        assert c.execute(text("UPDATE evidence_items SET content='pwned' WHERE id=:i"), {"i": b["evidence"]}).rowcount == 0
        assert c.execute(text("DELETE FROM evidence_items WHERE id=:i"), {"i": b["evidence"]}).rowcount == 0
        assert c.execute(text("DELETE FROM sources WHERE organization_id=:o"), {"o": b["org"]}).rowcount == 0
        assert c.execute(text("DELETE FROM audit_events")).rowcount == 1  # only A's own row
        c.rollback()
    with rls_db[engine_key].begin() as c:
        _as(c, b["org"])
        assert c.execute(text("SELECT content FROM evidence_items WHERE id=:i"), {"i": b["evidence"]}).scalar() == "secret of org b"


@pytest.mark.parametrize("engine_key", ["app", "ctl"])
def test_cannot_move_row_into_other_org(rls_db, engine_key):
    a, b = rls_db["orgs"]["a"], rls_db["orgs"]["b"]
    with rls_db[engine_key].connect() as c:
        with c.begin():
            _as(c, a["org"])
            with pytest.raises(DBAPIError, match="row-level security"):
                c.execute(text("UPDATE sources SET organization_id=:b WHERE id=:i"), {"b": b["org"], "i": a["source"]})


@pytest.mark.parametrize("engine_key", ["app", "ctl"])
def test_insert_for_other_org_or_without_org_rejected(rls_db, engine_key):
    a, b = rls_db["orgs"]["a"], rls_db["orgs"]["b"]
    sql = text("INSERT INTO sources (id, organization_id, name, source_type, scope, status, config, visibility_mode) "
               "VALUES (:i, :o, 'x', 'upload', 'organization', 'ready', '{}', 'all_members')")
    for scope_org in (a["org"], None):
        with rls_db[engine_key].connect() as c:
            with c.begin():
                _as(c, scope_org)
                with pytest.raises(DBAPIError, match="row-level security"):
                    c.execute(sql, {"i": uuid.uuid4(), "o": b["org"]})


def test_data_plane_role_sees_only_own_org_identity(rls_db):
    a = rls_db["orgs"]["a"]
    with rls_db["app"].begin() as c:
        assert c.execute(text("SELECT count(*) FROM users")).scalar() == 0
        _as(c, a["org"])
        assert {r[0] for r in c.execute(text("SELECT id FROM users"))} == {a["user"]}
        assert {r[0] for r in c.execute(text("SELECT id FROM organizations"))} == {a["org"]}
        assert {r[0] for r in c.execute(text("SELECT organization_id FROM organization_memberships"))} == {a["org"]}


def test_control_plane_role_cross_org_only_on_identity_tables(rls_db):
    a, b = rls_db["orgs"]["a"], rls_db["orgs"]["b"]
    with rls_db["ctl"].begin() as c:
        # login by email / invitations / org creation / super-admin need cross-org identity reads
        emails = {r[0] for r in c.execute(text("SELECT id FROM users WHERE id = ANY(:u)"), {"u": [a["user"], b["user"]]})}
        assert emails == {a["user"], b["user"]}
        assert c.execute(text("SELECT count(*) FROM organizations WHERE id = ANY(:o)"), {"o": [a["org"], b["org"]]}).scalar() == 2
        # ...but still no tenant data without an org
        assert c.execute(text("SELECT count(*) FROM evidence_items")).scalar() == 0


def test_orm_session_scope_hook_sets_org_each_transaction(rls_db):
    a, b = rls_db["orgs"]["a"], rls_db["orgs"]["b"]
    with Session(rls_db["app"]) as s:
        assert s.execute(text("SELECT count(*) FROM evidence_items")).scalar() == 0
        s.commit()
        scope_session_to_org(s, a["org"])
        assert s.execute(text("SELECT id FROM evidence_items")).scalars().all() == [a["evidence"]]
        s.commit()  # new transaction: hook must re-apply SET LOCAL
        assert s.execute(text("SELECT id FROM evidence_items")).scalars().all() == [a["evidence"]]
        s.commit()
        scope_session_to_org(s, b["org"])
        assert s.execute(text("SELECT id FROM evidence_items")).scalars().all() == [b["evidence"]]


def test_open_tenant_session_is_scoped_for_api_and_workers(rls_db, monkeypatch):
    """open_tenant_session (get_tenant_db + every Celery task) uses TENANT_DATABASE_URL and scopes."""
    from app.core.config import get_settings
    from app.tenant_store import resolver
    from app.tenant_store.pool import tenant_pool_manager

    a = rls_db["orgs"]["a"]
    monkeypatch.setattr(get_settings(), "tenant_database_url", _url_for(APP_ROLE))
    monkeypatch.setattr(resolver, "assert_schema_compatible", lambda s: None)
    tenant_pool_manager.dispose_all()
    with Session(rls_db["ctl"]) as control:
        sess = resolver.open_tenant_session(control, a["org"])
        try:
            assert sess.execute(text("SELECT current_user")).scalar() == APP_ROLE
            assert sess.execute(text("SELECT id FROM evidence_items")).scalars().all() == [a["evidence"]]
        finally:
            sess.close()
        control.rollback()
    tenant_pool_manager.dispose_all()

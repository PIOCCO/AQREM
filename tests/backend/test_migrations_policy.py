import inspect
import re

from sqlalchemy import text

from app.db import migrate


def test_versions_are_consecutive_and_documented():
    versions = [m.version for m in migrate.MIGRATIONS]
    assert versions == list(range(1, len(versions) + 1))
    assert all(m.rollback_note.strip() for m in migrate.MIGRATIONS)


def test_migrations_are_non_destructive():
    banned = re.compile(r"\b(DROP\s+TABLE|DROP\s+COLUMN|TRUNCATE|DROP\s+SCHEMA)\b", re.I)
    for m in migrate.MIGRATIONS:
        src = inspect.getsource(m.apply)
        assert not banned.search(src), f"migration {m.version} contains destructive DDL"


def test_runner_is_idempotent(engine):
    migrate.run_migrations(engine)
    assert migrate.pending(engine) == []
    assert migrate.run_migrations(engine) == []
    with engine.connect() as conn:
        assert migrate.applied_versions(conn) >= {m.version for m in migrate.MIGRATIONS}
        assert conn.execute(text("SELECT to_regclass('ix_evidence_items_org_source') IS NOT NULL")).scalar()


def test_ensure_app_role_creates_least_privilege_role(engine):
    import uuid

    from app.services.system.db_check import run_database_checks
    from sqlalchemy.engine import make_url
    from tests.backend.conftest import DATABASE_URL

    role = f"aq_app_{uuid.uuid4().hex[:8]}"
    migrate.ensure_app_role(engine, role, "Pw-test-12345")
    migrate.ensure_app_role(engine, role, "Pw-test-12345")  # idempotent
    try:
        url = make_url(DATABASE_URL).set(username=role, password="Pw-test-12345").render_as_string(hide_password=False)
        r = run_database_checks(url, role="app")
        checks = {c.name: c.status for c in r.checks}
        assert checks["permissions"] == "ok", r.to_dict()
        assert checks["least_privilege"] == "ok", r.to_dict()
        # The blanket DML grant must not re-open the schema guard (read-only) or license evidence (no DELETE).
        with engine.connect() as conn:
            def privs(table):
                return set(conn.execute(text(
                    "SELECT privilege_type FROM information_schema.role_table_grants "
                    "WHERE grantee = :r AND table_name = :t"), {"r": role, "t": table}).scalars())
            if conn.execute(text("SELECT to_regclass('aqrem_schema_guard')")).scalar():
                assert privs("aqrem_schema_guard") == {"SELECT"}
            assert privs("license_runtime_state") == {"SELECT", "INSERT", "UPDATE"}
    finally:
        with engine.begin() as conn:
            conn.execute(text(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM {role}"))
            conn.execute(text(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM {role}"))
            conn.execute(text(f"DROP OWNED BY {role}"))
            conn.execute(text(f"DROP ROLE {role}"))

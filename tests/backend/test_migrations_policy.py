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

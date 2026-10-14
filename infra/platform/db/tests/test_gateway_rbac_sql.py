"""Static and optional integration tests for gateway least-privilege DB role."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"


def test_gateway_role_revokes_platform_schema() -> None:
    sql = (MIGRATIONS / "003_gateway_least_privilege_role.sql").read_text(encoding="utf-8")
    assert "REVOKE ALL ON SCHEMA platform FROM aqrem_gateway_app" in sql
    assert "GRANT USAGE ON SCHEMA gateway TO aqrem_gateway_app" in sql


def test_platform_tables_not_in_gateway_schema() -> None:
    gateway = (MIGRATIONS / "002_gateway_schema.sql").read_text(encoding="utf-8").lower()
    assert "platform." not in gateway


@pytest.mark.integration
def test_gateway_role_cannot_select_platform_cells() -> None:
    """Requires TEST_GATEWAY_DATABASE_URL as gateway MI (or role member of aqrem_gateway_app)."""
    url = os.environ.get("TEST_GATEWAY_DATABASE_URL")
    if not url:
        pytest.skip("TEST_GATEWAY_DATABASE_URL not set")
    import psycopg

    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute("SELECT count(*) FROM platform.cells")
                cur.fetchone()

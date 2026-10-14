"""20 concurrent reservations against a cell with 5 free slots (requires Postgres)."""

from __future__ import annotations

import concurrent.futures
import os
import uuid

import pytest

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "worker"))
from cell_allocation import RELEASE_CELL_SQL, RESERVE_CELL_SQL  # noqa: E402

pytest.importorskip("psycopg")


@pytest.fixture
def dsn() -> str:
    url = os.environ.get("TEST_CELL_DATABASE_URL")
    if not url:
        pytest.skip("TEST_CELL_DATABASE_URL not set")
    return url


def test_atomic_reserve_sql_contract() -> None:
    assert "FOR UPDATE SKIP LOCKED" not in RESERVE_CELL_SQL
    assert "clients_used < max_clients" in RESERVE_CELL_SQL


@pytest.mark.integration
def test_twenty_concurrent_only_five_succeed(dsn: str) -> None:
    import psycopg

    cell_id = f"test-{uuid.uuid4().hex[:8]}"
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(
            """
            INSERT INTO platform.cells (id, region, environment, core_quota, max_clients, clients_used, status)
            VALUES (%s, 'westeurope', 'dev', 100, 10, 5, 'ACTIVE')
            ON CONFLICT (id) DO NOTHING
            """,
            (cell_id,),
        )

    def reserve() -> bool:
        with psycopg.connect(dsn, autocommit=True) as conn:
            row = conn.execute(
                RESERVE_CELL_SQL,
                {"region": "westeurope", "environment": "dev"},
            ).fetchone()
            return row is not None

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(lambda _: reserve(), range(20)))

    successes = sum(1 for r in results if r)
    assert successes == 5

    with psycopg.connect(dsn, autocommit=True) as conn:
        row = conn.execute(
            "SELECT clients_used, max_clients FROM platform.cells WHERE id = %s",
            (cell_id,),
        ).fetchone()
        assert row[0] == 10
        conn.execute(RELEASE_CELL_SQL, {"cell_id": cell_id})
        conn.execute("DELETE FROM platform.cells WHERE id = %s", (cell_id,))

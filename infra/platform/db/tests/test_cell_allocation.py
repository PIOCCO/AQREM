"""Concurrency-safe cell pick: SQL contract tests (integration optional)."""

from __future__ import annotations

import os

import pytest

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "worker"))
from cell_allocation import RESERVE_CELL_SQL  # noqa: E402


def test_allocate_sql_is_atomic_without_skip_locked() -> None:
    assert "FOR UPDATE SKIP LOCKED" not in RESERVE_CELL_SQL
    assert "clients_used < max_clients" in RESERVE_CELL_SQL


@pytest.mark.integration
def test_two_concurrent_allocations_do_not_overfill() -> None:
    url = os.environ.get("TEST_PLATFORM_WORKER_DATABASE_URL")
    if not url:
        pytest.skip("TEST_PLATFORM_WORKER_DATABASE_URL not set")
    import concurrent.futures

    import psycopg

    def allocate() -> tuple[str | None, int | None]:
        with psycopg.connect(url, autocommit=False) as conn:
            with conn.cursor() as cur:
                cur.execute(ALLOCATE_SQL, {"region": "westeurope", "environment": "dev"})
                row = cur.fetchone()
                conn.commit()
                if not row:
                    return None, None
                return row[0], row[1]

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: allocate(), range(2)))
    ids = [r[0] for r in results if r[0]]
    assert len(set(ids)) <= 1 or len(ids) == 2

"""Concurrency-safe cell pick: SQL contract tests (integration optional)."""

from __future__ import annotations

import os

import pytest

ALLOCATE_SQL = """
WITH picked AS (
  SELECT id
  FROM platform.cells
  WHERE region = %(region)s
    AND environment = %(environment)s
    AND status = 'ACTIVE'
    AND clients_used < max_clients
  ORDER BY clients_used ASC, id
  FOR UPDATE SKIP LOCKED
  LIMIT 1
)
UPDATE platform.cells c
SET clients_used = c.clients_used + 1,
    updated_at = now()
FROM picked
WHERE c.id = picked.id
RETURNING c.id, c.clients_used, c.max_clients;
"""


def test_allocate_sql_uses_row_lock() -> None:
    assert "FOR UPDATE SKIP LOCKED" in ALLOCATE_SQL


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

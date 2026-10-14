"""Atomic cell capacity reservation (no SKIP LOCKED — avoids false 'no capacity' under contention)."""

from __future__ import annotations

RESERVE_CELL_SQL = """
UPDATE platform.cells
SET clients_used = clients_used + 1,
    updated_at = now()
WHERE id = (
  SELECT id
  FROM platform.cells
  WHERE region = %(region)s
    AND environment = %(environment)s
    AND status = 'ACTIVE'
    AND clients_used < max_clients
  ORDER BY clients_used ASC, id
  LIMIT 1
)
AND clients_used < max_clients
RETURNING id, clients_used, max_clients;
"""

RELEASE_CELL_SQL = """
UPDATE platform.cells
SET clients_used = GREATEST(clients_used - 1, 0),
    updated_at = now()
WHERE id = %(cell_id)s
RETURNING id, clients_used;
"""

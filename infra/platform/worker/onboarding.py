"""
Idempotent client onboarding worker (control-plane DB only; no deployment secrets).

The product API enqueues work by inserting/updating platform.client_deployments;
this worker advances the state machine and calls external provisioners (Terraform GH Actions).
"""

from __future__ import annotations

import enum
import json
import os
import uuid
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.rows import dict_row

try:
    from cell_allocation import RELEASE_CELL_SQL, RESERVE_CELL_SQL
except ImportError:
    from .cell_allocation import RELEASE_CELL_SQL, RESERVE_CELL_SQL  # type: ignore


class DeploymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROVISIONING = "PROVISIONING"
    MIGRATING = "MIGRATING"
    VERIFYING = "VERIFYING"
    ACTIVE = "ACTIVE"
    FAILED = "FAILED"
    DECOMMISSIONING = "DECOMMISSIONING"
    DECOMMISSIONED = "DECOMMISSIONED"


@dataclass
class Deployment:
    deployment_id: uuid.UUID
    client_id: str
    status: DeploymentStatus
    current_step: str | None
    cell_id: str | None
    region: str
    plan: str
    db_mode: str


def connect() -> psycopg.Connection:
    url = os.environ["CONTROL_PLANE_DATABASE_URL"]
    return psycopg.connect(url, row_factory=dict_row)


def audit(conn: psycopg.Connection, *, actor: str, action: str, resource_type: str, resource_id: str, detail: dict[str, Any] | None = None) -> None:
    conn.execute(
        """
        INSERT INTO platform.audit_log (actor, action, resource_type, resource_id, detail)
        VALUES (%s, %s, %s, %s, %s::jsonb)
        """,
        (actor, action, resource_type, resource_id, json.dumps(detail or {})),
    )


def log_event(conn: psycopg.Connection, deployment_id: uuid.UUID, step: str, outcome: str, detail: str | None = None) -> None:
    conn.execute(
        """
        INSERT INTO platform.deployment_events (deployment_id, step, outcome, detail)
        VALUES (%s, %s, %s, %s)
        """,
        (deployment_id, step, outcome, detail),
    )


def pick_deployment(conn: psycopg.Connection) -> Deployment | None:
    row = conn.execute(
        """
        SELECT deployment_id, client_id, status, current_step, cell_id, region, plan, db_mode
        FROM platform.client_deployments
        WHERE status IN ('PENDING', 'PROVISIONING', 'MIGRATING', 'VERIFYING', 'FAILED')
        ORDER BY updated_at ASC
        FOR UPDATE SKIP LOCKED
        LIMIT 1
        """
    ).fetchone()
    if not row:
        return None
    return Deployment(
        deployment_id=row["deployment_id"],
        client_id=row["client_id"],
        status=DeploymentStatus(row["status"]),
        current_step=row["current_step"],
        cell_id=row["cell_id"],
        region=row["region"],
        plan=row["plan"],
        db_mode=row["db_mode"],
    )


def allocate_cell(conn: psycopg.Connection, *, region: str, environment: str) -> str | None:
    row = conn.execute(
        RESERVE_CELL_SQL,
        {"region": region, "environment": environment},
    ).fetchone()
    return row["id"] if row else None


def release_cell(conn: psycopg.Connection, cell_id: str) -> None:
    conn.execute(RELEASE_CELL_SQL, {"cell_id": cell_id})


def set_status(
    conn: psycopg.Connection,
    deployment_id: uuid.UUID,
    status: DeploymentStatus,
    *,
    step: str | None = None,
    error: str | None = None,
    cell_id: str | None = None,
) -> None:
    conn.execute(
        """
        UPDATE platform.client_deployments
        SET status = %s,
            current_step = COALESCE(%s, current_step),
            last_error = %s,
            cell_id = COALESCE(%s, cell_id),
            updated_at = now()
        WHERE deployment_id = %s
        """,
        (status.value, step, error, cell_id, deployment_id),
    )


def run_once(*, environment: str, actor: str = "onboarding-worker") -> bool:
    """Returns True if work was processed."""
    with connect() as conn:
        conn.execute("BEGIN")
        dep = pick_deployment(conn)
        if not dep:
            conn.execute("ROLLBACK")
            return False

        if dep.status in (DeploymentStatus.PENDING, DeploymentStatus.FAILED):
            cell_id = dep.cell_id or allocate_cell(conn, region=dep.region, environment=environment)
            if not cell_id:
                set_status(conn, dep.deployment_id, DeploymentStatus.FAILED, step="allocate_cell", error="No cell capacity")
                log_event(conn, dep.deployment_id, "allocate_cell", "FAILED", "No cell capacity")
                audit(conn, actor=actor, action="onboard.allocate_cell", resource_type="deployment", resource_id=str(dep.deployment_id), detail={"client_id": dep.client_id})
                conn.commit()
                return True
            set_status(conn, dep.deployment_id, DeploymentStatus.PROVISIONING, step="terraform_apply", cell_id=cell_id)
            log_event(conn, dep.deployment_id, "allocate_cell", "OK", cell_id)
            audit(conn, actor=actor, action="onboard.allocate_cell", resource_type="deployment", resource_id=str(dep.deployment_id), detail={"cell_id": cell_id})

        # Further steps (terraform, migrations, health checks) are invoked by GitHub Actions;
        # worker only records state transitions when callbacks arrive.
        conn.commit()
        return True


if __name__ == "__main__":
    env = os.environ.get("AQREM_ENVIRONMENT", "dev")
    processed = run_once(environment=env)
    print("processed=", processed)

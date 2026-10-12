"""Environment provisioning jobs (no automatic paid cloud deploy without adapter config)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.audit.service import record_audit
from app.core.config import get_settings
from app.models.environment import ClientEnvironment, ProvisioningJob
from app.models.organization import Organization


def _now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_environment_record(db: Session, org: Organization) -> ClientEnvironment:
    env = db.query(ClientEnvironment).filter(ClientEnvironment.organization_id == org.id).first()
    if env:
        return env
    env_id = f"env-{org.slug}-{str(org.id)[:8]}"
    env = ClientEnvironment(
        organization_id=org.id,
        environment_id=env_id,
        deployment_status="pending",
        license_status=org.license_status,
    )
    db.add(env)
    db.flush()
    return env


def start_provisioning_job(db: Session, *, org: Organization, admin_user_id: uuid.UUID) -> ProvisioningJob:
    settings = get_settings()
    adapter = (settings.app_env or "development").lower()
    env = ensure_environment_record(db, org)

    active = (
        db.query(ProvisioningJob)
        .filter(
            ProvisioningJob.organization_id == org.id,
            ProvisioningJob.status.in_(["queued", "running"]),
        )
        .first()
    )
    if active:
        return active

    job = ProvisioningJob(
        organization_id=org.id,
        environment_id=env.environment_id,
        status="queued",
        adapter="local" if adapter != "production" else "azure_unconfigured",
    )
    db.add(job)
    db.flush()
    record_audit(
        db,
        organization_id=org.id,
        user_id=admin_user_id,
        action="provisioning_job_created",
        resource_type="provisioning_job",
        resource_id=str(job.id),
        metadata={"adapter": job.adapter},
    )
    run_provisioning_job(db, job=job, org=org)
    return job


def run_provisioning_job(db: Session, *, job: ProvisioningJob, org: Organization) -> None:
    """Local adapter: record URLs only — never claim Azure success without integration."""
    job.status = "running"
    job.history = [*job.history, {"at": _now().isoformat(), "status": "running"}]
    env = db.query(ClientEnvironment).filter(ClientEnvironment.organization_id == org.id).one()

    settings = get_settings()
    base = settings.cors_allowed_origins.split(",")[0].strip() if settings.cors_allowed_origins else ""
    if not base:
        base = "http://localhost:5173"

    if job.adapter == "azure_unconfigured":
        job.status = "blocked"
        job.safe_error_summary = "Azure provisioning adapter is not configured for this deployment."
        env.deployment_status = "blocked"
        job.history = [*job.history, {"at": _now().isoformat(), "status": "blocked"}]
        return

    # Idempotent local registration of logical URLs (shared multi-tenant deployment).
    env.employee_url = f"{base}/chat"
    env.admin_url = f"{base}/admin"
    env.deployment_status = "ready"
    env.deployment_region = "local"
    env.application_version = "0.1.0"
    env.health_status = "healthy"
    env.last_health_check_at = _now()
    env.license_status = org.license_status
    job.status = "succeeded"
    job.history = [*job.history, {"at": _now().isoformat(), "status": "succeeded"}]


def retry_provisioning_job(db: Session, *, job: ProvisioningJob, org: Organization, admin_user_id: uuid.UUID) -> ProvisioningJob:
    if job.status in {"succeeded", "running"}:
        return job
    job.retry_count += 1
    job.status = "queued"
    job.safe_error_summary = None
    record_audit(
        db,
        organization_id=org.id,
        user_id=admin_user_id,
        action="provisioning_job_retried",
        resource_type="provisioning_job",
        resource_id=str(job.id),
        metadata={"retry_count": job.retry_count},
    )
    run_provisioning_job(db, job=job, org=org)
    return job

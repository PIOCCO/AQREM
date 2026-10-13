"""Platform master console — metadata only, no customer content endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.platform_access import require_platform_permission
from app.models.environment import ClientEnvironment, ControlPlaneEvent, ProvisioningJob
from app.models.organization import Organization, User
from app.services.admin_org import org_to_admin_response
from app.services.provisioning.service import retry_provisioning_job, start_provisioning_job
from app.services.telemetry import TelemetryRejected, validate_control_plane_payload
from app.db.session import get_db

router = APIRouter()


@router.get("/environments")
def list_environments(
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_permission("deployment:read")),
) -> list[dict]:
    rows = db.query(ClientEnvironment, Organization).join(Organization, Organization.id == ClientEnvironment.organization_id).all()
    return [
        {
            "organization_id": str(env.organization_id),
            "organization_name": org.name,
            "environment_id": env.environment_id,
            "employee_url": env.employee_url,
            "admin_url": env.admin_url,
            "deployment_status": env.deployment_status,
            "deployment_region": env.deployment_region,
            "application_version": env.application_version,
            "health_status": env.health_status,
            "last_health_check_at": env.last_health_check_at,
            "license_status": env.license_status,
        }
        for env, org in rows
    ]


@router.get("/organizations/{organization_id}/environment")
def get_environment_detail(
    organization_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_permission("deployment:read")),
) -> dict:
    env = db.query(ClientEnvironment).filter(ClientEnvironment.organization_id == organization_id).first()
    org = db.get(Organization, organization_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    jobs = (
        db.query(ProvisioningJob)
        .filter(ProvisioningJob.organization_id == organization_id)
        .order_by(ProvisioningJob.created_at.desc())
        .limit(20)
        .all()
    )
    events = (
        db.query(ControlPlaneEvent)
        .filter(ControlPlaneEvent.organization_id == organization_id)
        .order_by(ControlPlaneEvent.created_at.desc())
        .limit(50)
        .all()
    )
    return {
        "organization": org_to_admin_response(db, org).model_dump(),
        "environment": None
        if env is None
        else {
            "environment_id": env.environment_id,
            "employee_url": env.employee_url,
            "admin_url": env.admin_url,
            "deployment_status": env.deployment_status,
            "deployment_region": env.deployment_region,
            "application_version": env.application_version,
            "health_status": env.health_status,
            "last_health_check_at": env.last_health_check_at,
        },
        "provisioning_jobs": [
            {
                "id": str(j.id),
                "status": j.status,
                "adapter": j.adapter,
                "safe_error_summary": j.safe_error_summary,
                "retry_count": j.retry_count,
                "updated_at": j.updated_at,
            }
            for j in jobs
        ],
        "telemetry": [
            {"event_type": e.event_type, "payload": e.payload, "created_at": e.created_at} for e in events
        ],
    }


@router.post("/organizations/{organization_id}/provision")
def provision_organization(
    organization_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_permission("deployment:provision")),
) -> dict:
    org = db.get(Organization, organization_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    job = start_provisioning_job(db, org=org, admin_user_id=admin.id)
    db.commit()
    return {"job_id": str(job.id), "status": job.status, "adapter": job.adapter}


@router.post("/provisioning-jobs/{job_id}/retry")
def retry_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_permission("deployment:retry")),
) -> dict:
    job = db.get(ProvisioningJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    org = db.get(Organization, job.organization_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    job = retry_provisioning_job(db, job=job, org=org, admin_user_id=admin.id)
    db.commit()
    return {"job_id": str(job.id), "status": job.status}


@router.post("/telemetry")
def ingest_telemetry(
    payload: dict,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_permission("telemetry:ingest")),
) -> dict:
    """Allowlisted operational events only (no document or conversation content)."""
    event_type = str(payload.get("event_type", ""))
    org_id = payload.get("organization_id")
    env_id = payload.get("environment_id")
    body = payload.get("payload") or {}
    try:
        safe = validate_control_plane_payload(event_type, body if isinstance(body, dict) else {})
    except TelemetryRejected as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not org_id:
        raise HTTPException(status_code=400, detail="organization_id required")
    event = ControlPlaneEvent(
        organization_id=UUID(str(org_id)),
        environment_id=str(env_id) if env_id else None,
        event_type=event_type,
        payload=safe,
    )
    db.add(event)
    db.commit()
    return {"accepted": True, "event_type": event_type}

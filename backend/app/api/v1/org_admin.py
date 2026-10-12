"""Client organization admin console (data plane — tenant scoped)."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_tenant_context, require_org_admin
from app.core.tenant import TenantContext
from app.db.session import get_db
from app.models.organization import Organization
from app.services.setup_checklist import build_setup_checklist

router = APIRouter()


@router.get("/setup")
def get_setup_checklist(
    tenant: TenantContext = Depends(require_org_admin),
    db: Session = Depends(get_db),
) -> dict:
    return build_setup_checklist(db, organization_id=tenant.organization_id)


@router.get("/overview")
def org_admin_overview(
    tenant: TenantContext = Depends(require_org_admin),
    db: Session = Depends(get_db),
) -> dict:
    org = db.get(Organization, tenant.organization_id)
    checklist = build_setup_checklist(db, organization_id=tenant.organization_id)
    return {
        "organization": {
            "id": str(org.id) if org else None,
            "name": org.name if org else "",
            "license_limit": org.license_limit if org else 0,
            "license_status": org.license_status if org else "",
        },
        "setup": checklist,
        "employee_workspace_path": "/chat",
        "admin_console_path": "/admin",
    }

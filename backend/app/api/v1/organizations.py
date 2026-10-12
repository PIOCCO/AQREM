from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_tenant_context
from app.core.tenant import TenantContext
from app.db.session import get_db
from app.models.organization import Organization, OrganizationMembership
from app.schemas.organization import OrganizationResponse

router = APIRouter()


@router.get("", response_model=list[OrganizationResponse])
def list_organizations(
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> list[Organization]:
    org_ids = [
        m.organization_id
        for m in db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.user_id == tenant.user_id,
            OrganizationMembership.is_active.is_(True),
        )
        .all()
    ]
    return db.query(Organization).filter(Organization.id.in_(org_ids)).all()

import re

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_tenant_context, require_role
from app.core.roles import Role
from app.core.tenant import TenantContext
from app.db.session import get_db
from app.models.organization import Organization, OrganizationMembership
from app.schemas.organization import OrganizationCreate, OrganizationResponse

router = APIRouter()


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "org"


@router.get("", response_model=list[OrganizationResponse])
def list_organizations(
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> list[Organization]:
    org_ids = [
        m.organization_id
        for m in db.query(OrganizationMembership)
        .filter(OrganizationMembership.user_id == tenant.user_id)
        .all()
    ]
    return db.query(Organization).filter(Organization.id.in_(org_ids)).all()


@router.post("", response_model=OrganizationResponse)
def create_organization(
    payload: OrganizationCreate,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> Organization:
    org = Organization(name=payload.name, slug=_slugify(payload.name))
    db.add(org)
    db.flush()
    db.add(
        OrganizationMembership(
            organization_id=org.id,
            user_id=tenant.user_id,
            role=Role.ORG_ADMIN.value,
        )
    )
    db.commit()
    db.refresh(org)
    return org

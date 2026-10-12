from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_platform_admin
from app.core.roles import Role
from app.db.session import get_db
from app.models.organization import Organization, OrganizationMembership, User
from app.schemas.admin import (
    AdminMembershipResponse,
    AdminOrganizationCreate,
    AdminOrganizationResponse,
    AdminOrganizationUpdate,
    AdminProvisionUserRequest,
    AdminProvisionUserResponse,
)
from app.services.licensing import count_active_seats
from app.services.platform_provisioning import (
    create_organization_admin,
    deactivate_membership,
    deactivate_user_account,
    provision_user_invitation,
    set_organization_license,
    unique_org_slug,
)

router = APIRouter()


def _org_response(db: Session, org: Organization) -> AdminOrganizationResponse:
    return AdminOrganizationResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        license_limit=org.license_limit,
        license_status=org.license_status,
        is_active=org.is_active,
        active_seats=count_active_seats(db, org.id),
    )


@router.get("/organizations", response_model=list[AdminOrganizationResponse])
def list_organizations_admin(
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_admin),
) -> list[AdminOrganizationResponse]:
    orgs = db.query(Organization).order_by(Organization.created_at.desc()).all()
    return [_org_response(db, o) for o in orgs]


@router.post("/organizations", response_model=AdminOrganizationResponse, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: AdminOrganizationCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_admin),
) -> AdminOrganizationResponse:
    slug = payload.slug or unique_org_slug(db, payload.name)
    if db.query(Organization).filter(Organization.slug == slug).first():
        raise HTTPException(status_code=400, detail="Organization slug already exists")
    org = create_organization_admin(
        db,
        admin_user_id=admin.id,
        name=payload.name,
        slug=slug,
        license_limit=payload.license_limit,
        license_status=payload.license_status,
    )
    db.commit()
    db.refresh(org)
    return _org_response(db, org)


@router.patch("/organizations/{organization_id}", response_model=AdminOrganizationResponse)
def update_organization(
    organization_id: UUID,
    payload: AdminOrganizationUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_admin),
) -> AdminOrganizationResponse:
    org = db.get(Organization, organization_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    try:
        set_organization_license(
            db,
            admin_user_id=admin.id,
            org=org,
            license_limit=payload.license_limit,
            license_status=payload.license_status,
            is_active=payload.is_active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(org)
    return _org_response(db, org)


@router.get("/organizations/{organization_id}/members", response_model=list[AdminMembershipResponse])
def list_members(
    organization_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_admin),
) -> list[AdminMembershipResponse]:
    rows = (
        db.query(OrganizationMembership, User)
        .join(User, User.id == OrganizationMembership.user_id)
        .filter(OrganizationMembership.organization_id == organization_id)
        .all()
    )
    return [
        AdminMembershipResponse(
            id=membership.id,
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=Role(membership.role),
            is_active=membership.is_active,
            user_is_active=user.is_active,
        )
        for membership, user in rows
    ]


@router.post(
    "/organizations/{organization_id}/users",
    response_model=AdminProvisionUserResponse,
    status_code=status.HTTP_201_CREATED,
)
def provision_user(
    organization_id: UUID,
    payload: AdminProvisionUserRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_admin),
) -> AdminProvisionUserResponse:
    try:
        user, _membership, raw_token, expires_at = provision_user_invitation(
            db,
            admin_user_id=admin.id,
            organization_id=organization_id,
            email=payload.email.lower(),
            full_name=payload.full_name,
            role=payload.role,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    setup_path = f"/accept-invite?token={raw_token}"
    return AdminProvisionUserResponse(
        user_id=user.id,
        organization_id=organization_id,
        email=user.email,
        role=payload.role,
        invitation_expires_at=expires_at,
        invitation_setup_path=setup_path,
    )


@router.post("/organizations/{organization_id}/members/{membership_id}/deactivate", status_code=204)
def deactivate_member(
    organization_id: UUID,
    membership_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_admin),
) -> None:
    membership = db.get(OrganizationMembership, membership_id)
    if membership is None or membership.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Membership not found")
    deactivate_membership(db, admin_user_id=admin.id, membership=membership)
    db.commit()


@router.post("/users/{user_id}/deactivate", status_code=204)
def deactivate_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_admin),
) -> None:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        deactivate_user_account(db, admin_user_id=admin.id, user=user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.admin_errors import admin_error
from app.core.dependencies import require_platform_admin
from app.core.roles import Role
from app.db.session import get_db
from app.models.audit import AuditEvent
from app.models.enums import LicenseStatus
from app.models.invitation import UserInvitation
from app.models.organization import Organization, OrganizationMembership, User
from app.schemas.admin import (
    AdminAuditListResponse,
    AdminAuditRow,
    AdminContextResponse,
    AdminDirectoryResponse,
    AdminDirectoryRow,
    AdminInvitationResponse,
    AdminMemberRoleUpdate,
    AdminMembershipResponse,
    AdminOrganizationCreate,
    AdminOrganizationListResponse,
    AdminOrganizationResponse,
    AdminOrganizationUpdate,
    AdminProvisionUserRequest,
    AdminProvisionUserResponse,
)
from app.services.admin_org import (
    filter_orgs_for_admin,
    get_admin_visible_org,
    org_status_bucket,
    org_to_admin_response,
    seat_usage_response,
)
from app.services.licensing import LicenseDenied, assert_can_add_seat, licensing_test_mode_effective
from app.services.platform_provisioning import (
    create_organization_admin,
    deactivate_membership,
    provision_user_invitation,
    resend_invitation,
    revoke_invitation,
    set_organization_license,
    unique_org_slug,
    update_membership_role,
)
from app.services.seat_usage import get_seat_usage

router = APIRouter()


def _require_admin_visible_org(db: Session, organization_id: UUID) -> Organization:
    org = get_admin_visible_org(db, organization_id)
    if org is None:
        raise admin_error(code="NOT_FOUND", message="Organization not found", status_code=404)
    return org


@router.get("/context", response_model=AdminContextResponse)
def admin_context(admin: User = Depends(require_platform_admin)) -> AdminContextResponse:
    effective = licensing_test_mode_effective()
    return AdminContextResponse(licensing_test_mode=effective, test_mode_effective=effective)


def _counts(orgs: list[Organization]) -> dict[str, int]:
    counts = {"all": len(orgs), "active": 0, "suspended": 0, "test": 0}
    for org in orgs:
        bucket = org_status_bucket(org)
        counts[bucket] = counts.get(bucket, 0) + 1
    return counts


@router.get("/organizations", response_model=AdminOrganizationListResponse)
def list_organizations_admin(
    q: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_admin),
) -> AdminOrganizationListResponse:
    orgs = db.query(Organization).order_by(Organization.name.asc()).all()
    orgs = filter_orgs_for_admin(orgs)
    if q:
        needle = q.strip().lower()
        orgs = [o for o in orgs if needle in o.name.lower() or needle in o.slug.lower()]
    if status_filter and status_filter != "all":
        orgs = [o for o in orgs if org_status_bucket(o) == status_filter]
    items = [org_to_admin_response(db, o) for o in orgs]
    visible = filter_orgs_for_admin(db.query(Organization).all())
    return AdminOrganizationListResponse(items=items, counts=_counts(visible))


@router.get("/organizations/{organization_id}", response_model=AdminOrganizationResponse)
def get_organization(
    organization_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_admin),
) -> AdminOrganizationResponse:
    org = _require_admin_visible_org(db, organization_id)
    return org_to_admin_response(db, org)


@router.post("/organizations", response_model=AdminOrganizationResponse, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: AdminOrganizationCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_admin),
) -> AdminOrganizationResponse:
    env = payload.environment.strip().lower()
    if env == "test":
        if not licensing_test_mode_effective():
            raise admin_error(
                code="TEST_MODE_DISABLED",
                message="Test organizations are not available in this environment",
                field="environment",
            )
        license_status = LicenseStatus.TEST
    elif env == "production":
        license_status = LicenseStatus.ACTIVE
    else:
        raise admin_error(code="INVALID_ENVIRONMENT", message="Invalid environment", field="environment")

    slug = payload.slug or unique_org_slug(db, payload.name)
    if db.query(Organization).filter(Organization.slug == slug).first():
        raise admin_error(code="DUPLICATE_SLUG", message="Organization slug already exists", field="name")

    org = create_organization_admin(
        db,
        admin_user_id=admin.id,
        name=payload.name,
        slug=slug,
        license_limit=payload.license_limit,
        license_status=license_status,
        owner_display_name=payload.owner_display_name,
    )
    db.commit()
    db.refresh(org)
    return org_to_admin_response(db, org)


@router.patch("/organizations/{organization_id}", response_model=AdminOrganizationResponse)
def update_organization(
    organization_id: UUID,
    payload: AdminOrganizationUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_admin),
) -> AdminOrganizationResponse:
    org = _require_admin_visible_org(db, organization_id)

    usage = get_seat_usage(db, org)
    if payload.license_limit is not None and payload.license_limit < usage.seats_used:
        raise admin_error(
            code="LIMIT_BELOW_USAGE",
            message=f"Seat limit cannot be below current usage ({usage.seats_used} seats in use)",
            field="license_limit",
        )

    if payload.license_status == LicenseStatus.TEST and not licensing_test_mode_effective():
        raise admin_error(
            code="TEST_MODE_DISABLED",
            message="Test license status is not available",
            field="license_status",
        )

    try:
        set_organization_license(
            db,
            admin_user_id=admin.id,
            org=org,
            license_limit=payload.license_limit,
            license_status=payload.license_status,
            is_active=payload.is_active,
        )
        if payload.owner_display_name is not None:
            org.owner_display_name = payload.owner_display_name
    except ValueError as exc:
        raise admin_error(code="VALIDATION_ERROR", message=str(exc)) from exc
    db.commit()
    db.refresh(org)
    return org_to_admin_response(db, org)


@router.get("/organizations/{organization_id}/directory", response_model=AdminDirectoryResponse)
def organization_directory(
    organization_id: UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=5, ge=1, le=50),
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_admin),
) -> AdminDirectoryResponse:
    org = _require_admin_visible_org(db, organization_id)

    usage = get_seat_usage(db, org)
    rows: list[AdminDirectoryRow] = []

    member_rows = (
        db.query(OrganizationMembership, User)
        .join(User, User.id == OrganizationMembership.user_id)
        .filter(OrganizationMembership.organization_id == organization_id)
        .order_by(User.full_name.asc())
        .all()
    )
    for membership, user in member_rows:
        status_label = "Active" if membership.is_active and user.is_active else "Inactive"
        rows.append(
            AdminDirectoryRow(
                row_id=f"m-{membership.id}",
                kind="member",
                membership_id=membership.id,
                user_id=user.id,
                full_name=user.full_name,
                email=user.email,
                role=Role(membership.role),
                status=status_label,
            )
        )

    now = datetime.now(timezone.utc)
    invites = (
        db.query(UserInvitation)
        .filter(
            UserInvitation.organization_id == organization_id,
            UserInvitation.used_at.is_(None),
            UserInvitation.revoked_at.is_(None),
            UserInvitation.expires_at > now,
        )
        .order_by(UserInvitation.created_at.desc())
        .all()
    )
    for inv in invites:
        rows.append(
            AdminDirectoryRow(
                row_id=f"i-{inv.id}",
                kind="invitation",
                invitation_id=inv.id,
                full_name="—",
                email=inv.email,
                role=Role(inv.role),
                status="Pending invite",
            )
        )

    total = len(rows)
    start = (page - 1) * page_size
    page_rows = rows[start : start + page_size]

    from app.services.admin_org import license_renews_at

    return AdminDirectoryResponse(
        seats=seat_usage_response(usage),
        license_status=org.license_status,
        license_renews_at=license_renews_at(org),
        rows=page_rows,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/organizations/{organization_id}/invitations", response_model=list[AdminInvitationResponse])
def list_invitations(
    organization_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_admin),
) -> list[AdminInvitationResponse]:
    _require_admin_visible_org(db, organization_id)
    now = datetime.now(timezone.utc)
    invites = (
        db.query(UserInvitation)
        .filter(
            UserInvitation.organization_id == organization_id,
            UserInvitation.used_at.is_(None),
            UserInvitation.revoked_at.is_(None),
            UserInvitation.expires_at > now,
        )
        .order_by(UserInvitation.expires_at.asc())
        .all()
    )
    return [
        AdminInvitationResponse(
            id=inv.id,
            email=inv.email,
            role=Role(inv.role),
            expires_at=inv.expires_at,
            created_at=inv.created_at,
        )
        for inv in invites
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
    _require_admin_visible_org(db, organization_id)
    try:
        user, _membership, invitation, raw_token, expires_at = provision_user_invitation(
            db,
            admin_user_id=admin.id,
            organization_id=organization_id,
            email=payload.email.lower(),
            full_name=payload.full_name,
            role=payload.role,
        )
    except LicenseDenied:
        raise admin_error(
            code="SEATS_FULL",
            message="No seats left. Increase the seat limit or remove a member.",
            field="email",
            status_code=403,
        ) from None
    except ValueError as exc:
        if str(exc) == "DUPLICATE_EMAIL":
            raise admin_error(
                code="DUPLICATE_EMAIL",
                message="A pending invitation already exists for this email",
                field="email",
            ) from exc
        raise admin_error(code="VALIDATION_ERROR", message=str(exc)) from exc
    db.commit()
    return AdminProvisionUserResponse(
        user_id=user.id,
        organization_id=organization_id,
        email=user.email,
        role=payload.role,
        invitation_id=invitation.id,
        invitation_expires_at=expires_at,
        invitation_setup_path=f"/accept-invite?token={raw_token}",
    )


@router.post("/organizations/{organization_id}/invitations/{invitation_id}/resend", response_model=AdminProvisionUserResponse)
def resend_user_invitation(
    organization_id: UUID,
    invitation_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_admin),
) -> AdminProvisionUserResponse:
    invitation = db.get(UserInvitation, invitation_id)
    if invitation is None or invitation.organization_id != organization_id:
        raise admin_error(code="NOT_FOUND", message="Invitation not found", status_code=404)
    org = _require_admin_visible_org(db, organization_id)
    try:
        assert_can_add_seat(db, org)
    except LicenseDenied:
        raise admin_error(code="SEATS_FULL", message="No seats available", status_code=403) from None

    raw_token, expires_at = resend_invitation(db, admin_user_id=admin.id, invitation=invitation)
    user = db.query(User).filter(User.email == invitation.email).first()
    db.commit()
    return AdminProvisionUserResponse(
        user_id=user.id if user else invitation.id,
        organization_id=organization_id,
        email=invitation.email,
        role=Role(invitation.role),
        invitation_id=invitation.id,
        invitation_expires_at=expires_at,
        invitation_setup_path=f"/accept-invite?token={raw_token}",
    )


@router.post("/organizations/{organization_id}/invitations/{invitation_id}/revoke", status_code=204)
def revoke_user_invitation(
    organization_id: UUID,
    invitation_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_admin),
) -> None:
    _require_admin_visible_org(db, organization_id)
    invitation = db.get(UserInvitation, invitation_id)
    if invitation is None or invitation.organization_id != organization_id:
        raise admin_error(code="NOT_FOUND", message="Invitation not found", status_code=404)
    revoke_invitation(db, admin_user_id=admin.id, invitation=invitation)
    db.commit()


@router.get("/organizations/{organization_id}/members", response_model=list[AdminMembershipResponse])
def list_members(
    organization_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_admin),
) -> list[AdminMembershipResponse]:
    _require_admin_visible_org(db, organization_id)
    rows = (
        db.query(OrganizationMembership, User)
        .join(User, User.id == OrganizationMembership.user_id)
        .filter(OrganizationMembership.organization_id == organization_id)
        .order_by(User.full_name.asc())
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


@router.patch("/organizations/{organization_id}/members/{membership_id}", response_model=AdminMembershipResponse)
def patch_member_role(
    organization_id: UUID,
    membership_id: UUID,
    payload: AdminMemberRoleUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_admin),
) -> AdminMembershipResponse:
    _require_admin_visible_org(db, organization_id)
    membership = db.get(OrganizationMembership, membership_id)
    if membership is None or membership.organization_id != organization_id:
        raise admin_error(code="NOT_FOUND", message="Membership not found", status_code=404)
    user = db.get(User, membership.user_id)
    if user is None:
        raise admin_error(code="NOT_FOUND", message="User not found", status_code=404)
    update_membership_role(db, admin_user_id=admin.id, membership=membership, role=payload.role)
    db.commit()
    return AdminMembershipResponse(
        id=membership.id,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=Role(membership.role),
        is_active=membership.is_active,
        user_is_active=user.is_active,
    )


@router.post("/organizations/{organization_id}/members/{membership_id}/deactivate", status_code=204)
def deactivate_member(
    organization_id: UUID,
    membership_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_admin),
) -> None:
    _require_admin_visible_org(db, organization_id)
    membership = db.get(OrganizationMembership, membership_id)
    if membership is None or membership.organization_id != organization_id:
        raise admin_error(code="NOT_FOUND", message="Membership not found", status_code=404)
    deactivate_membership(db, admin_user_id=admin.id, membership=membership)
    db.commit()


@router.get("/organizations/{organization_id}/audit", response_model=AdminAuditListResponse)
def list_org_audit(
    organization_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_admin),
) -> AdminAuditListResponse:
    _require_admin_visible_org(db, organization_id)
    events = (
        db.query(AuditEvent, User)
        .outerjoin(User, User.id == AuditEvent.user_id)
        .filter(AuditEvent.organization_id == organization_id)
        .order_by(AuditEvent.created_at.desc())
        .limit(limit)
        .all()
    )
    items = [
        AdminAuditRow(
            id=event.id,
            created_at=event.created_at,
            actor_email=user.email if user else None,
            action=event.action.replace("_", " "),
            target=f"{event.resource_type} {event.resource_id or ''}".strip(),
        )
        for event, user in events
    ]
    return AdminAuditListResponse(items=items)

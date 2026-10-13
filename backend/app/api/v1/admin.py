import secrets
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.admin_errors import admin_error
from app.core.platform_access import require_platform_permission, resolve_platform_role
from app.core.platform_roles import PlatformRole
from app.core.permissions_catalog import platform_permission_matrix, platform_endpoint_permissions
from app.services.platform_staff import (
    PlatformStaffError,
    count_active_super_admins,
    invite_platform_staff,
    set_platform_role,
)
from app.services.roles_audit import run_roles_audit
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
    DeactivateMemberRequest,
    AdminProvisionUserRequest,
    AdminProvisionUserResponse,
    PermissionsMatrixResponse,
    PlatformStaffInviteRequest,
    PlatformStaffRoleUpdate,
    PlatformStaffRow,
    ReplaceOrgAdminRequest,
    RolesAuditReport,
)
from app.services.admin_org import (
    filter_orgs_for_admin,
    get_admin_visible_org,
    org_status_bucket,
    org_to_admin_response,
    seat_usage_response,
)
from app.audit.service import record_audit
from app.services.licensing import LicenseDenied, assert_can_add_seat, licensing_test_mode_effective
from app.services.platform_provisioning import (
    create_organization_admin,
    deactivate_membership,
    set_organization_license,
    unique_org_slug,
    update_membership_role,
)
from app.services.invitations.admin_invitation import provision_admin_invitation, resend_admin_invitation
from app.services.platform_provisioning import revoke_invitation
from app.services.access_control.groups import ensure_default_access_groups
from app.tenant_store.resolver import open_tenant_session
from app.api.v1 import admin_invitations
from app.services.seat_usage import get_seat_usage

router = APIRouter()
router.include_router(admin_invitations.router)


def _require_admin_visible_org(db: Session, organization_id: UUID) -> Organization:
    org = get_admin_visible_org(db, organization_id)
    if org is None:
        raise admin_error(code="NOT_FOUND", message="Organization not found", status_code=404)
    return org


@router.get("/context", response_model=AdminContextResponse)
def admin_context(
    admin: User = Depends(require_platform_permission("org:read")),
    db: Session = Depends(get_db),
) -> AdminContextResponse:
    effective = licensing_test_mode_effective()
    super_count = count_active_super_admins(db)
    return AdminContextResponse(
        licensing_test_mode=effective,
        test_mode_effective=effective,
        active_super_admin_count=super_count,
        super_admin_warning=super_count < 2,
    )


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
    admin: User = Depends(require_platform_permission("org:read")),
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
    admin: User = Depends(require_platform_permission("org:read")),
) -> AdminOrganizationResponse:
    org = _require_admin_visible_org(db, organization_id)
    return org_to_admin_response(db, org)


@router.post("/organizations", response_model=AdminOrganizationResponse, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: AdminOrganizationCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_permission("org:create")),
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
    tenant_db = open_tenant_session(db, org.id)
    try:
        ensure_default_access_groups(tenant_db, org.id)
        tenant_db.commit()
    finally:
        tenant_db.close()
    db.commit()
    db.refresh(org)
    return org_to_admin_response(db, org)


@router.patch("/organizations/{organization_id}", response_model=AdminOrganizationResponse)
def update_organization(
    organization_id: UUID,
    payload: AdminOrganizationUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_permission("org:update")),
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
    admin: User = Depends(require_platform_permission("org:read")),
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
        seats=seat_usage_response(org, usage),
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
    admin: User = Depends(require_platform_permission("invitation:read")),
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
    admin: User = Depends(require_platform_permission("invitation:create_admin")),
) -> AdminProvisionUserResponse:
    _require_admin_visible_org(db, organization_id)
    if payload.role != Role.ORG_ADMIN:
        raise admin_error(
            code="ROLE_NOT_ALLOWED",
            message="Platform staff may only invite an organization administrator.",
            field="role",
        )
    try:
        user, _membership, invitation, raw_token, expires_at, _email_sent = provision_admin_invitation(
            db,
            admin_user_id=admin.id,
            organization_id=organization_id,
            email=payload.email.lower(),
            full_name=payload.full_name,
        )
    except LicenseDenied as exc:
        reason = exc.detail or ""
        if "No licensed seats" in reason or "license_limit is zero" in reason:
            raise admin_error(
                code="NO_LICENSED_SEATS",
                message="This organization has no licensed seats. Increase the seat limit on the License tab.",
                field="email",
                status_code=403,
            ) from None
        if "license is not active" in reason or "deactivated" in reason.lower():
            raise admin_error(
                code="LICENSE_INACTIVE",
                message=reason,
                field="email",
                status_code=403,
            ) from None
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
        if str(exc) == "EMAIL_IN_OTHER_ORG":
            raise admin_error(
                code="EMAIL_IN_OTHER_ORG",
                message="This email already belongs to a user in another organization.",
                field="email",
            ) from exc
        raise admin_error(code="VALIDATION_ERROR", message=str(exc)) from exc
    db.commit()
    return AdminProvisionUserResponse(
        user_id=user.id,
        organization_id=organization_id,
        email=user.email,
        role=Role.ORG_ADMIN,
        invitation_id=invitation.id,
        invitation_expires_at=expires_at,
        invitation_setup_path=f"/accept-invite?token={raw_token}",
    )


@router.post("/organizations/{organization_id}/invitations/{invitation_id}/resend", response_model=AdminProvisionUserResponse)
def resend_user_invitation(
    organization_id: UUID,
    invitation_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_permission("invitation:create_admin")),
) -> AdminProvisionUserResponse:
    invitation = db.get(UserInvitation, invitation_id)
    if invitation is None or invitation.organization_id != organization_id:
        raise admin_error(code="NOT_FOUND", message="Invitation not found", status_code=404)
    org = _require_admin_visible_org(db, organization_id)
    try:
        assert_can_add_seat(db, org)
    except LicenseDenied:
        raise admin_error(code="SEATS_FULL", message="No seats available", status_code=403) from None

    raw_token, expires_at = resend_admin_invitation(db, admin_user_id=admin.id, invitation=invitation)
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
    admin: User = Depends(require_platform_permission("invitation:revoke")),
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
    admin: User = Depends(require_platform_permission("org:read")),
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
    admin: User = Depends(require_platform_permission("org_admin:replace")),
) -> AdminMembershipResponse:
    _require_admin_visible_org(db, organization_id)
    membership = db.get(OrganizationMembership, membership_id)
    if membership is None or membership.organization_id != organization_id:
        raise admin_error(code="NOT_FOUND", message="Membership not found", status_code=404)
    user = db.get(User, membership.user_id)
    if user is None:
        raise admin_error(code="NOT_FOUND", message="User not found", status_code=404)
    if payload.role != Role.ORG_ADMIN:
        raise admin_error(
            code="ROLE_NOT_ALLOWED",
            message="Platform staff may only assign the organization administrator role.",
            field="role",
        )
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
    payload: DeactivateMemberRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_permission("org_member:deactivate")),
) -> None:
    _require_admin_visible_org(db, organization_id)
    membership = db.get(OrganizationMembership, membership_id)
    if membership is None or membership.organization_id != organization_id:
        raise admin_error(code="NOT_FOUND", message="Membership not found", status_code=404)
    reason = payload.reason.strip()
    active_admins = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.is_active.is_(True),
            OrganizationMembership.role == Role.ORG_ADMIN.value,
        )
        .count()
    )
    if membership.role == Role.ORG_ADMIN.value and membership.is_active and active_admins <= 1:
        raise admin_error(
            code="LAST_ORG_ADMIN",
            message="Cannot remove the last organization admin without replacing them first",
            status_code=409,
        )
    deactivate_membership(db, admin_user_id=admin.id, membership=membership, reason=reason)
    db.commit()


@router.get("/organizations/{organization_id}/audit", response_model=AdminAuditListResponse)
def list_org_audit(
    organization_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_permission("org:audit_read")),
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


@router.get("/permissions/matrix", response_model=PermissionsMatrixResponse)
def permissions_matrix(
    _admin: User = Depends(require_platform_permission("platform_permissions:read")),
) -> PermissionsMatrixResponse:
    endpoints = platform_endpoint_permissions()
    perms = sorted({p for p in endpoints.values()})
    matrix = platform_permission_matrix()
    return PermissionsMatrixResponse(
        permissions=perms,
        roles=list(matrix.keys()),
        matrix=matrix,
        endpoints=endpoints,
    )


@router.get("/roles/audit", response_model=RolesAuditReport)
def roles_audit(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_platform_permission("roles:audit_run")),
) -> RolesAuditReport:
    report = run_roles_audit(db)
    return RolesAuditReport(**report)


@router.get("/platform-staff", response_model=list[PlatformStaffRow])
def list_platform_staff(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_platform_permission("platform_staff:read")),
) -> list[PlatformStaffRow]:
    rows: list[PlatformStaffRow] = []
    for user in db.query(User).order_by(User.full_name.asc()).all():
        role = resolve_platform_role(user)
        if role is None:
            continue
        status_label = "Active" if user.is_active else "Suspended"
        rows.append(
            PlatformStaffRow(
                id=user.id,
                email=user.email,
                full_name=user.full_name,
                platform_role=role.value,
                status=status_label,
                created_at=user.created_at,
            )
        )
    return rows


@router.post("/platform-staff/invite", response_model=PlatformStaffRow, status_code=status.HTTP_201_CREATED)
def invite_staff(
    payload: PlatformStaffInviteRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_permission("platform_staff:invite")),
) -> PlatformStaffRow:
    try:
        role = PlatformRole(payload.role.strip().upper())
    except ValueError as exc:
        raise admin_error(code="INVALID_ROLE", message="Unknown platform role", field="role") from exc
    temp_password = secrets.token_urlsafe(16)
    try:
        user = invite_platform_staff(
            db,
            actor_id=admin.id,
            email=payload.email.lower(),
            full_name=payload.full_name,
            role=role,
            temp_password=temp_password,
        )
    except PlatformStaffError as exc:
        raise admin_error(code=str(exc), message=str(exc).replace("_", " ").capitalize()) from exc
    db.commit()
    return PlatformStaffRow(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        platform_role=role.value,
        status="Active",
        created_at=user.created_at,
    )


@router.patch("/platform-staff/{user_id}", response_model=PlatformStaffRow)
def update_staff_role(
    user_id: UUID,
    payload: PlatformStaffRoleUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_permission("platform_staff:update")),
) -> PlatformStaffRow:
    target = db.get(User, user_id)
    if target is None or resolve_platform_role(target) is None:
        raise admin_error(code="NOT_FOUND", message="Platform staff member not found", status_code=404)
    try:
        new_role = PlatformRole(payload.role.strip().upper())
    except ValueError as exc:
        raise admin_error(code="INVALID_ROLE", message="Unknown platform role", field="role") from exc
    try:
        set_platform_role(db, actor_id=admin.id, target=target, role=new_role, reason=payload.reason)
    except PlatformStaffError as exc:
        raise admin_error(code=str(exc), message=str(exc).replace("_", " ").capitalize()) from exc
    db.commit()
    db.refresh(target)
    role = resolve_platform_role(target)
    assert role is not None
    return PlatformStaffRow(
        id=target.id,
        email=target.email,
        full_name=target.full_name,
        platform_role=role.value,
        status="Active" if target.is_active else "Suspended",
        created_at=target.created_at,
    )


@router.post(
    "/organizations/{organization_id}/replace-org-admin",
    response_model=AdminProvisionUserResponse,
    status_code=status.HTTP_201_CREATED,
)
def replace_org_admin(
    organization_id: UUID,
    payload: ReplaceOrgAdminRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_permission("org_admin:replace")),
) -> AdminProvisionUserResponse:
    org = _require_admin_visible_org(db, organization_id)
    for membership, user in (
        db.query(OrganizationMembership, User)
        .join(User, User.id == OrganizationMembership.user_id)
        .filter(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.role == Role.ORG_ADMIN.value,
            OrganizationMembership.is_active.is_(True),
        )
        .all()
    ):
        update_membership_role(db, admin_user_id=admin.id, membership=membership, role=Role.EDITOR)
        record_audit(
            db,
            organization_id=organization_id,
            user_id=admin.id,
            action="org_admin_replaced_demoted",
            resource_type="organization_membership",
            resource_id=str(membership.id),
            metadata={"previous_user_id": str(user.id), "reason": payload.reason, "source": "platform_control_plane"},
        )
    try:
        user, _membership, invitation, raw_token, expires_at, _sent = provision_admin_invitation(
            db,
            admin_user_id=admin.id,
            organization_id=organization_id,
            email=payload.email.lower(),
            full_name=payload.full_name,
        )
    except LicenseDenied as exc:
        raise admin_error(code="SEATS_FULL", message=str(exc.detail or "No seats available"), status_code=403) from exc
    except ValueError as exc:
        if str(exc) == "EMAIL_IN_OTHER_ORG":
            raise admin_error(
                code="EMAIL_IN_OTHER_ORG",
                message="This email already belongs to a user in another organization.",
                field="email",
            ) from exc
        raise admin_error(code="VALIDATION_ERROR", message=str(exc)) from exc
    record_audit(
        db,
        organization_id=organization_id,
        user_id=admin.id,
        action="org_admin_replaced",
        resource_type="organization",
        resource_id=str(org.id),
        metadata={"new_admin_email": payload.email.lower(), "reason": payload.reason, "source": "platform_control_plane"},
    )
    db.commit()
    return AdminProvisionUserResponse(
        user_id=user.id,
        organization_id=organization_id,
        email=user.email,
        role=Role.ORG_ADMIN,
        invitation_id=invitation.id,
        invitation_expires_at=expires_at,
        invitation_setup_path=f"/accept-invite?token={raw_token}",
    )

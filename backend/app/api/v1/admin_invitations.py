"""Platform organization invitations (admin + employee link)."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.admin_errors import admin_error
from app.core.platform_access import require_platform_permission
from app.core.roles import Role
from app.db.session import get_db
from app.models.invitation import UserInvitation
from app.models.organization import OrganizationMembership, User
from app.models.employee_join import EmployeeJoinLink
from app.schemas.invitations import (
    AdminInvitationCreateRequest,
    AdminInvitationCreateResponse,
    AdminInvitationHistoryRow,
    EmployeeLinkCreateRequest,
    EmployeeLinkCreateResponse,
    EmployeeLinkSummary,
    InvitationLinkResponse,
    InvitationsSetupStatus,
)
from app.services.admin_org import get_admin_visible_org, seat_usage_response
from app.services.email.invitations import email_delivery_configured
from app.services.invitations.admin_invitation import (
    delete_admin_invitation,
    invitation_public_status,
    invitation_setup_path,
    invitation_setup_url,
    provision_admin_invitation,
    reissue_admin_invitation,
    resend_admin_invitation,
    resolve_admin_invitation_link,
)
from app.services.invitations.employee_join import (
    create_employee_join_link,
    delete_employee_join_link,
    get_active_link_for_org,
    join_setup_path,
    join_setup_url,
    resolve_employee_join_link,
    rotate_employee_link,
    set_link_status,
    LINK_DISABLED,
    LINK_PAUSED,
)
from app.services.invitations.invite_urls import absolute_from_invite_path, try_absolute_from_invite_path
from app.services.invitations.token_vault import unseal_invitation_token
from app.services.licensing import LicenseDenied
from app.services.platform_provisioning import revoke_invitation
from app.services.seat_usage import get_seat_usage

router = APIRouter()


def _admin_link_response(*, path: str, expires_at: datetime | None, request: Request) -> InvitationLinkResponse:
    return InvitationLinkResponse(
        invitation_setup_path=path,
        invitation_setup_url=absolute_from_invite_path(path, request=request),
        expires_at=expires_at,
    )


def _employee_link_response(*, path: str, expires_at: datetime | None, request: Request) -> InvitationLinkResponse:
    return InvitationLinkResponse(
        join_path=path,
        join_url=absolute_from_invite_path(path, request=request),
        expires_at=expires_at,
    )


def _history_invite_urls_admin(inv: UserInvitation, *, request: Request) -> tuple[str | None, str | None]:
    if inv.used_at is not None or not inv.token_ciphertext:
        return None, None
    try:
        raw = unseal_invitation_token(inv.token_ciphertext)
        path = invitation_setup_path(raw)
        return path, try_absolute_from_invite_path(path, request=request)
    except ValueError:
        return None, None


def _history_invite_urls_employee(link: EmployeeJoinLink, *, request: Request) -> tuple[str | None, str | None]:
    if not link.token_ciphertext:
        return None, None
    try:
        raw = unseal_invitation_token(link.token_ciphertext)
        path = join_setup_path(raw)
        return path, try_absolute_from_invite_path(path, request=request)
    except ValueError:
        return None, None


def _visible_org(db: Session, organization_id: UUID):
    org = get_admin_visible_org(db, organization_id)
    if org is None:
        raise admin_error(code="NOT_FOUND", message="Organization not found", status_code=404)
    return org


@router.get("/organizations/{organization_id}/invitations/setup", response_model=InvitationsSetupStatus)
def invitations_setup_status(
    organization_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_permission("invitation:read")),
) -> InvitationsSetupStatus:
    org = _visible_org(db, organization_id)
    usage = get_seat_usage(db, org)
    now = datetime.now(timezone.utc)
    admin_inv = (
        db.query(UserInvitation)
        .filter(
            UserInvitation.organization_id == organization_id,
            or_(
                UserInvitation.invitation_kind == "org_admin",
                UserInvitation.role == Role.ORG_ADMIN.value,
            ),
        )
        .order_by(UserInvitation.created_at.desc())
        .first()
    )
    admin_status = "none"
    admin_email = None
    admin_accepted = False
    pending_org_admin_invite = False
    if admin_inv:
        admin_status = invitation_public_status(admin_inv, now=now)
        admin_email = admin_inv.email
        admin_accepted = admin_inv.used_at is not None
        pending_org_admin_invite = admin_status == "pending"
    active_admin = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.role == Role.ORG_ADMIN.value,
            OrganizationMembership.is_active.is_(True),
        )
        .first()
    )
    link = get_active_link_for_org(db, organization_id)
    return InvitationsSetupStatus(
        admin_invitation_status=admin_status,
        admin_invitation_email=admin_email,
        admin_accepted=admin_accepted,
        has_active_org_admin=active_admin is not None,
        pending_org_admin_invite=pending_org_admin_invite,
        employee_link_status=link.status if link else None,
        employee_link_joined_count=link.joined_count if link else 0,
        employee_link_pending_count=link.pending_approval_count if link else 0,
        seats=seat_usage_response(org, usage).model_dump(),
    )


def _employee_link_history_status(link: EmployeeJoinLink, *, now: datetime) -> str:
    exp = link.expires_at
    if exp is not None:
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < now:
            return "expired"
    if link.status == LINK_DISABLED:
        return "revoked"
    if link.status == LINK_PAUSED:
        return "paused"
    return "pending"


@router.get("/organizations/{organization_id}/invitations/history", response_model=list[AdminInvitationHistoryRow])
def invitation_history(
    organization_id: UUID,
    request: Request,
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_permission("invitation:read")),
) -> list[AdminInvitationHistoryRow]:
    _visible_org(db, organization_id)

    now = datetime.now(timezone.utc)
    invites = (
        db.query(UserInvitation)
        .filter(
            UserInvitation.organization_id == organization_id,
            or_(
                UserInvitation.invitation_kind == "org_admin",
                UserInvitation.role == Role.ORG_ADMIN.value,
            ),
        )
        .order_by(UserInvitation.created_at.desc())
        .limit(200)
        .all()
    )
    links = (
        db.query(EmployeeJoinLink)
        .filter(EmployeeJoinLink.organization_id == organization_id)
        .order_by(EmployeeJoinLink.created_at.desc())
        .limit(50)
        .all()
    )
    rows: list[AdminInvitationHistoryRow] = []
    for inv in invites:
        st = invitation_public_status(inv, now=now)
        if status_filter and status_filter != "all" and st != status_filter:
            continue
        inv_path, inv_url = _history_invite_urls_admin(inv, request=request)
        rows.append(
            AdminInvitationHistoryRow(
                id=inv.id,
                record_type="admin_invitation",
                kind=inv.invitation_kind or "org_admin",
                email=inv.email,
                role=Role(inv.role),
                status=st,
                invitee_full_name=inv.invitee_full_name,
                expires_at=inv.expires_at,
                created_at=inv.created_at,
                accepted_at=inv.used_at,
                revoked_at=inv.revoked_at,
                created_by_user_id=inv.created_by_user_id,
                invite_path=inv_path,
                invite_url=inv_url,
            )
        )
    for link in links:
        st = _employee_link_history_status(link, now=now)
        filter_status = st if st != "paused" else "pending"
        if status_filter and status_filter != "all" and filter_status != status_filter:
            continue
        domain_hint = ", ".join(link.allowed_domains or []) or "Any email (approval required)"
        link_path, link_url = _history_invite_urls_employee(link, request=request)
        rows.append(
            AdminInvitationHistoryRow(
                id=link.id,
                record_type="employee_link",
                kind="employee_link",
                email=f"Employee link · {domain_hint}",
                role=Role.VIEWER,
                status=st,
                invitee_full_name=None,
                expires_at=link.expires_at,
                created_at=link.created_at,
                accepted_at=None,
                revoked_at=link.disabled_at,
                created_by_user_id=link.created_by_user_id,
                joined_count=link.joined_count,
                pending_approval_count=link.pending_approval_count,
                invite_path=link_path,
                invite_url=link_url,
            )
        )
    rows.sort(key=lambda r: r.created_at, reverse=True)
    return rows


@router.post(
    "/organizations/{organization_id}/invitations/admin",
    response_model=AdminInvitationCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_admin_invitation(
    organization_id: UUID,
    payload: AdminInvitationCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_permission("invitation:create_admin")),
) -> AdminInvitationCreateResponse:
    _visible_org(db, organization_id)
    try:
        user, _m, invitation, raw_token, expires_at, email_sent = provision_admin_invitation(
            db,
            admin_user_id=admin.id,
            organization_id=organization_id,
            email=payload.email.lower(),
            full_name=payload.full_name,
            personal_message=payload.personal_message,
            expires_days=payload.expires_days,
        )
    except LicenseDenied:
        raise admin_error(code="SEATS_FULL", message="No seats left.", status_code=403) from None
    except ValueError as exc:
        code = str(exc)
        if code == "DUPLICATE_EMAIL":
            raise admin_error(code=code, message="A pending invitation already exists for this email", field="email") from exc
        if code == "EMAIL_IN_OTHER_ORG":
            raise admin_error(
                code=code,
                message="This email already belongs to a user in another organization.",
                field="email",
            ) from exc
        if code == "ORG_ADMIN_EXISTS":
            raise admin_error(
                code=code,
                message="This organization already has an active organization admin.",
                status_code=409,
            ) from exc
        if code == "ORG_ADMIN_INVITE_PENDING":
            raise admin_error(
                code=code,
                message="A pending organization admin invitation already exists. Revoke or delete it first.",
                status_code=409,
            ) from exc
        raise admin_error(code="VALIDATION_ERROR", message=str(exc)) from exc
    db.commit()
    return AdminInvitationCreateResponse(
        user_id=user.id,
        organization_id=organization_id,
        email=user.email,
        role=Role.ORG_ADMIN,
        invitation_id=invitation.id,
        invitation_expires_at=expires_at,
        invitation_setup_path=invitation_setup_path(raw_token),
        invitation_setup_url=invitation_setup_url(raw_token, request=request),
        email_sent=email_sent,
    )


@router.get(
    "/organizations/{organization_id}/invitations/admin/{invitation_id}/link",
    response_model=InvitationLinkResponse,
)
def get_admin_invitation_link(
    organization_id: UUID,
    invitation_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_permission("invitation:read")),
) -> InvitationLinkResponse:
    _visible_org(db, organization_id)
    invitation = db.get(UserInvitation, invitation_id)
    if invitation is None or invitation.organization_id != organization_id:
        raise admin_error(code="NOT_FOUND", message="Invitation not found", status_code=404)
    st = invitation_public_status(invitation)
    try:
        if st == "pending":
            path = resolve_admin_invitation_link(invitation)
        elif st in {"expired", "revoked"}:
            raw, expires_at = reissue_admin_invitation(db, admin_user_id=admin.id, invitation=invitation)
            db.commit()
            path = invitation_setup_path(raw)
            return _admin_link_response(path=path, expires_at=expires_at, request=request)
        else:
            raise admin_error(code="INVALID_STATE", message="Accepted invitations cannot expose a link.", status_code=400)
    except ValueError as exc:
        if str(exc) == "LINK_UNAVAILABLE":
            raw, expires_at = reissue_admin_invitation(db, admin_user_id=admin.id, invitation=invitation)
            db.commit()
            path = invitation_setup_path(raw)
            return _admin_link_response(path=path, expires_at=expires_at, request=request)
        raise admin_error(code="INVALID_STATE", message=str(exc), status_code=400) from exc
    db.commit()
    return _admin_link_response(path=path, expires_at=invitation.expires_at, request=request)


def _delete_admin_invitation_impl(
    db: Session,
    *,
    organization_id: UUID,
    invitation_id: UUID,
    admin: User,
) -> None:
    _visible_org(db, organization_id)
    invitation = db.get(UserInvitation, invitation_id)
    if invitation is None or invitation.organization_id != organization_id:
        raise admin_error(code="NOT_FOUND", message="Invitation not found", status_code=404)
    try:
        delete_admin_invitation(db, admin_user_id=admin.id, invitation=invitation)
    except ValueError as exc:
        raise admin_error(code="INVALID_STATE", message=str(exc), status_code=400) from exc
    db.commit()


@router.delete("/organizations/{organization_id}/invitations/admin/{invitation_id}", status_code=204)
def delete_admin_invitation_row(
    organization_id: UUID,
    invitation_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_permission("invitation:revoke")),
) -> None:
    _delete_admin_invitation_impl(db, organization_id=organization_id, invitation_id=invitation_id, admin=admin)


@router.post(
    "/organizations/{organization_id}/invitations/admin/{invitation_id}/delete",
    status_code=204,
)
def delete_admin_invitation_row_post(
    organization_id: UUID,
    invitation_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_permission("invitation:revoke")),
) -> None:
    _delete_admin_invitation_impl(db, organization_id=organization_id, invitation_id=invitation_id, admin=admin)


@router.get(
    "/organizations/{organization_id}/employee-link/{link_id}/link",
    response_model=InvitationLinkResponse,
)
def get_employee_link_url(
    organization_id: UUID,
    link_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_permission("invitation:read")),
) -> InvitationLinkResponse:
    _visible_org(db, organization_id)
    link = db.get(EmployeeJoinLink, link_id)
    if link is None or link.organization_id != organization_id:
        raise admin_error(code="NOT_FOUND", message="Link not found", status_code=404)
    try:
        path = resolve_employee_join_link(link)
    except ValueError:
        raw = rotate_employee_link(db, admin_user_id=admin.id, link=link)
        db.commit()
        path = join_setup_path(raw)
        return _employee_link_response(path=path, expires_at=link.expires_at, request=request)
    db.commit()
    return _employee_link_response(path=path, expires_at=link.expires_at, request=request)


def _delete_employee_link_impl(
    db: Session,
    *,
    organization_id: UUID,
    link_id: UUID,
    admin: User,
) -> None:
    _visible_org(db, organization_id)
    link = db.get(EmployeeJoinLink, link_id)
    if link is None or link.organization_id != organization_id:
        raise admin_error(code="NOT_FOUND", message="Link not found", status_code=404)
    delete_employee_join_link(db, admin_user_id=admin.id, link=link)
    db.commit()


@router.delete("/organizations/{organization_id}/employee-link/{link_id}", status_code=204)
def delete_employee_link_row(
    organization_id: UUID,
    link_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_permission("invitation:revoke")),
) -> None:
    _delete_employee_link_impl(db, organization_id=organization_id, link_id=link_id, admin=admin)


@router.post("/organizations/{organization_id}/employee-link/{link_id}/delete", status_code=204)
def delete_employee_link_row_post(
    organization_id: UUID,
    link_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_permission("invitation:revoke")),
) -> None:
    _delete_employee_link_impl(db, organization_id=organization_id, link_id=link_id, admin=admin)


@router.get("/organizations/{organization_id}/employee-link", response_model=EmployeeLinkSummary)
def get_employee_link_summary(
    organization_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_permission("invitation:read")),
) -> EmployeeLinkSummary:
    _visible_org(db, organization_id)
    link = get_active_link_for_org(db, organization_id)
    if link is None:
        return EmployeeLinkSummary(
            link_id=None,
            status=None,
            joined_count=0,
            pending_approval_count=0,
            max_joins=None,
            expires_at=None,
            allowed_domains=[],
            require_admin_approval=False,
        )
    return EmployeeLinkSummary(
        link_id=link.id,
        status=link.status,
        joined_count=link.joined_count,
        pending_approval_count=link.pending_approval_count,
        max_joins=link.max_joins,
        expires_at=link.expires_at,
        allowed_domains=list(link.allowed_domains or []),
        require_admin_approval=link.require_admin_approval,
    )


@router.post(
    "/organizations/{organization_id}/employee-link",
    response_model=EmployeeLinkCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_employee_link(
    organization_id: UUID,
    payload: EmployeeLinkCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_permission("invitation:create_employee_link")),
) -> EmployeeLinkCreateResponse:
    _visible_org(db, organization_id)
    require_approval = payload.require_admin_approval
    if require_approval is None:
        require_approval = not bool(payload.allowed_domains)
    try:
        link, raw = create_employee_join_link(
            db,
            admin_user_id=admin.id,
            organization_id=organization_id,
            allowed_domains=payload.allowed_domains,
            require_admin_approval=require_approval,
            max_joins=payload.max_joins,
            expires_days=payload.expires_days,
        )
    except ValueError as exc:
        if str(exc) == "DOMAINS_OR_APPROVAL_REQUIRED":
            raise admin_error(
                code="POLICY_REQUIRED",
                message="Set allowed email domains or require admin approval for every joiner.",
            ) from exc
        raise admin_error(code="VALIDATION_ERROR", message=str(exc)) from exc
    db.commit()
    return EmployeeLinkCreateResponse(
        link_id=link.id,
        join_path=join_setup_path(raw),
        join_url=join_setup_url(raw, request=request),
        expires_at=link.expires_at,
        require_admin_approval=link.require_admin_approval,
        allowed_domains=list(link.allowed_domains or []),
        max_joins=link.max_joins,
        email_delivery_configured=email_delivery_configured(),
    )


@router.post("/organizations/{organization_id}/employee-link/{link_id}/rotate", response_model=EmployeeLinkCreateResponse)
def rotate_link(
    organization_id: UUID,
    link_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_permission("invitation:rotate")),
) -> EmployeeLinkCreateResponse:
    _visible_org(db, organization_id)
    link = db.get(EmployeeJoinLink, link_id)
    if link is None or link.organization_id != organization_id:
        raise admin_error(code="NOT_FOUND", message="Link not found", status_code=404)
    raw = rotate_employee_link(db, admin_user_id=admin.id, link=link)
    db.commit()
    return EmployeeLinkCreateResponse(
        link_id=link.id,
        join_path=join_setup_path(raw),
        join_url=join_setup_url(raw, request=request),
        expires_at=link.expires_at,
        require_admin_approval=link.require_admin_approval,
        allowed_domains=list(link.allowed_domains or []),
        max_joins=link.max_joins,
        email_delivery_configured=email_delivery_configured(),
    )


@router.post("/organizations/{organization_id}/employee-link/{link_id}/pause", status_code=204)
def pause_link(
    organization_id: UUID,
    link_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_permission("invitation:revoke")),
) -> None:
    _visible_org(db, organization_id)
    link = db.get(EmployeeJoinLink, link_id)
    if link is None or link.organization_id != organization_id:
        raise admin_error(code="NOT_FOUND", message="Link not found", status_code=404)
    set_link_status(db, admin_user_id=admin.id, link=link, status=LINK_PAUSED)
    db.commit()


@router.post("/organizations/{organization_id}/employee-link/{link_id}/resume", status_code=204)
def resume_link(
    organization_id: UUID,
    link_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_permission("invitation:create_employee_link")),
) -> None:
    _visible_org(db, organization_id)
    link = db.get(EmployeeJoinLink, link_id)
    if link is None or link.organization_id != organization_id:
        raise admin_error(code="NOT_FOUND", message="Link not found", status_code=404)
    set_link_status(db, admin_user_id=admin.id, link=link, status="active")
    db.commit()


@router.post("/organizations/{organization_id}/employee-link/{link_id}/disable", status_code=204)
def disable_link(
    organization_id: UUID,
    link_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_permission("invitation:revoke")),
) -> None:
    _visible_org(db, organization_id)
    link = db.get(EmployeeJoinLink, link_id)
    if link is None or link.organization_id != organization_id:
        raise admin_error(code="NOT_FOUND", message="Link not found", status_code=404)
    set_link_status(db, admin_user_id=admin.id, link=link, status=LINK_DISABLED)
    db.commit()

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.dependencies import get_authenticated_user, get_tenant_context
from app.core.uuid_parse import parse_optional_uuid
from app.core.permissions import permissions_for_role
from app.core.permissions_catalog import platform_permissions_for_role
from app.core.platform_access import resolve_platform_role
from app.core.platform_roles import PlatformRole
from app.core.rate_limit import AUTH_LOGIN_LIMIT, limiter
from app.core.roles import Role
from app.core.jwt_audiences import AUD_EMPLOYEE, AUD_ORG_ADMIN, AUD_PLATFORM, TENANT_AUDIENCES, ALL_AUDIENCES
from app.core.security import create_access_token, decode_access_token, hash_password, verify_password
from app.services.auth.password_reset import (
    PASSWORD_RESET_GENERIC_MESSAGE,
    request_password_reset,
    reset_password_with_token,
)
from app.core.tenant import TenantContext
from app.db.session import get_db
from app.models.organization import Organization, OrganizationMembership, User
from app.schemas.admin import (
    AcceptInvitationRequest,
    AcceptInvitationSendVerificationRequest,
    AcceptInvitationSendVerificationResponse,
    ChangePasswordRequest,
)
from app.services.invitations.admin_invitation_accept import send_admin_accept_verification
from app.schemas.invitations import AcceptInvitationPreviewRequest, AcceptInvitationPreviewResponse
from app.services.invitations.accept_preview import accept_invitation_requires_verification, preview_accept_invitation
from app.schemas.auth import ForgotPasswordRequest, LoginRequest, ResetPasswordRequest, TokenResponse, UserResponse
from app.services.licensing import org_allows_sign_in

logger = logging.getLogger("aqrem.auth")
from app.services.platform_provisioning import accept_invitation

router = APIRouter()
_me_bearer = HTTPBearer(auto_error=False)


@router.post("/login", response_model=TokenResponse)
@limiter.limit(AUTH_LOGIN_LIMIT)
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if user is None or not user.is_active or not user.hashed_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

    # Platform administrators may sign in without selecting an organization (admin console).
    platform_role = resolve_platform_role(user)
    if platform_role is not None and payload.organization_id is None:
        token = create_access_token(
            str(user.id),
            {
                "platform_role": platform_role.value,
                "platform_auth_version": int(getattr(user, "platform_auth_version", 1) or 1),
            },
            audience=AUD_PLATFORM,
        )
        return TokenResponse(
            access_token=token,
            organization_id=None,
            role=None,
            must_change_password=user.must_change_password,
            is_platform_admin=platform_role is not None,
        )

    membership_query = db.query(OrganizationMembership).filter(
        OrganizationMembership.user_id == user.id,
        OrganizationMembership.is_active.is_(True),
    )
    if payload.organization_id:
        membership_query = membership_query.filter(
            OrganizationMembership.organization_id == payload.organization_id
        )
    membership = membership_query.order_by(OrganizationMembership.id.asc()).first()
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No organization membership")

    org = db.get(Organization, membership.organization_id)
    if org is None or not org.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization not available")

    allowed, reason = org_allows_sign_in(org)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason)

    member_role = Role(membership.role)
    audience = AUD_ORG_ADMIN if member_role == Role.ORG_ADMIN else AUD_EMPLOYEE
    token = create_access_token(
        str(user.id),
        {
            "organization_id": str(membership.organization_id),
            "role": membership.role,
            "auth_version": membership.auth_version,
        },
        audience=audience,
    )
    return TokenResponse(
        access_token=token,
        organization_id=membership.organization_id,
        role=member_role,
        must_change_password=user.must_change_password,
        is_platform_admin=user.is_platform_admin,
    )


@router.post("/accept-invitation/preview", response_model=AcceptInvitationPreviewResponse)
@limiter.limit("30/minute")
def accept_invite_preview(
    request: Request,
    payload: AcceptInvitationPreviewRequest,
    db: Session = Depends(get_db),
) -> AcceptInvitationPreviewResponse:
    try:
        invitation, org = preview_accept_invitation(db, token=payload.token)
    except ValueError as exc:
        _preview_messages = {
            "Invalid invitation": "This invitation link is not valid.",
            "Invitation already used": "This invitation was already accepted. Try signing in.",
            "Invitation revoked": "This invitation was revoked. Ask for a new invite.",
            "Invitation expired": "This invitation has expired. Ask for a new invite.",
            "Organization unavailable": "This organization is no longer available.",
        }
        message = _preview_messages.get(str(exc), "This invitation is not valid.")
        raise HTTPException(status_code=404, detail={"message": message}) from exc
    return AcceptInvitationPreviewResponse(
        organization_name=org.name,
        role=Role(invitation.role),
        email=invitation.email,
        invitee_full_name=invitation.invitee_full_name,
        verification_required=accept_invitation_requires_verification(invitation),
    )


@router.post("/accept-invitation/send-verification", response_model=AcceptInvitationSendVerificationResponse)
@limiter.limit("30/minute")
def accept_invite_send_verification(
    request: Request,
    payload: AcceptInvitationSendVerificationRequest,
    db: Session = Depends(get_db),
) -> AcceptInvitationSendVerificationResponse:
    try:
        _inv, _org, dev = send_admin_accept_verification(
            db,
            token=payload.token.strip(),
            email=str(payload.email),
        )
    except ValueError as exc:
        code = str(exc)
        if code == "EMAIL_MISMATCH":
            raise HTTPException(status_code=400, detail={"message": "Email does not match this invitation."}) from exc
        if code == "RATE_LIMIT":
            from app.core.config import get_settings

            cooldown = int(get_settings().verification_resend_cooldown_seconds)
            raise HTTPException(
                status_code=429,
                detail={
                    "message": f"Please wait at least {cooldown} seconds before requesting another code.",
                    "retry_after_seconds": cooldown,
                },
                headers={"Retry-After": str(cooldown)},
            ) from exc
        if code == "VERIFICATION_NOT_REQUIRED":
            return AcceptInvitationSendVerificationResponse(verification_required=False, email_delivered=None)
        if code.startswith("EMAIL_SEND_FAILED:"):
            err = code.split(":", 1)[1]
            hint = err
            if "401" in err or "unrecognised ip" in err.lower() or "unrecognized ip" in err.lower():
                hint = (
                    "Email could not be sent (Brevo rejected the server IP). "
                    "Allow the API server IP in Brevo Authorized IPs, then click Resend code."
                )
            raise HTTPException(
                status_code=502,
                detail={"message": hint, "email_error": err[:500]},
            ) from exc
        raise HTTPException(status_code=404, detail={"message": "This invitation is not valid."}) from None
    db.commit()
    return AcceptInvitationSendVerificationResponse(
        verification_required=True,
        dev_verification_code=dev,
        email_delivered=True,
    )


@router.post("/accept-invitation", response_model=TokenResponse)
@limiter.limit(AUTH_LOGIN_LIMIT)
def accept_invite(
    request: Request,
    payload: AcceptInvitationRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    try:
        user, membership = accept_invitation(
            db,
            token=payload.token.strip(),
            email=str(payload.email),
            verification_code=payload.verification_code,
            password=payload.password,
            full_name=payload.full_name,
        )
    except ValueError as exc:
        if str(exc) == "PLATFORM_ACCOUNT":
            raise HTTPException(
                status_code=400,
                detail={"message": "This email is a platform administrator account and cannot accept an organization invitation."},
            ) from exc
        if str(exc) == "VERIFICATION_REQUIRED":
            raise HTTPException(
                status_code=400,
                detail={"message": "Send a verification code to your email first, then enter it here."},
            ) from exc
        if str(exc) == "VERIFICATION_EXPIRED":
            raise HTTPException(
                status_code=400,
                detail={"message": "That verification code expired. Click Resend code and use the newest email."},
            ) from exc
        if str(exc) == "VERIFICATION_LOCKED":
            raise HTTPException(
                status_code=400,
                detail={"message": "Too many wrong codes. Click Resend code to get a new one."},
            ) from exc
        if str(exc) == "VERIFICATION_INVALID":
            raise HTTPException(
                status_code=400,
                detail={"message": "That verification code is incorrect. Use the code from your latest email."},
            ) from exc
        if str(exc) in {"EMAIL_MISMATCH"}:
            raise HTTPException(status_code=400, detail={"message": "Verification failed for this invitation."}) from exc
        if str(exc).startswith("ORG_SIGNIN_BLOCKED:"):
            reason = str(exc).split(":", 1)[1]
            raise HTTPException(status_code=403, detail={"message": reason}) from exc
        if str(exc) in {"Organization deleted", "Organization unavailable"}:
            raise HTTPException(
                status_code=403,
                detail={"message": "This organization is no longer available. Ask your platform team for a new invitation."},
            ) from exc
        _accept_messages = {
            "Invalid invitation": "This invitation link is not valid. Open the latest link from your email or ask for a new invite.",
            "Invitation already used": "This invitation was already accepted. Try signing in with your password.",
            "Invitation revoked": "This invitation was revoked. Ask your platform team to send a new one.",
            "Invitation expired": "This invitation has expired. Ask your platform team to send a new one.",
            "User not found for invitation": "Account setup is incomplete. Ask your platform team to resend the invitation.",
            "Membership missing for invitation": "Organization membership is missing. Ask your platform team to resend the invitation.",
        }
        if str(exc) in _accept_messages:
            raise HTTPException(status_code=400, detail={"message": _accept_messages[str(exc)]}) from exc
        logger.warning("accept_invitation unmapped error: %s", exc)
        raise HTTPException(status_code=400, detail={"message": "This invitation is not valid."}) from exc
    db.commit()

    org = db.get(Organization, membership.organization_id)
    if org is None:
        raise HTTPException(status_code=400, detail={"message": "This invitation is not valid."})

    member_role = Role(membership.role)
    audience = AUD_ORG_ADMIN if member_role == Role.ORG_ADMIN else AUD_EMPLOYEE
    token = create_access_token(
        str(user.id),
        {
            "organization_id": str(membership.organization_id),
            "role": membership.role,
            "auth_version": membership.auth_version,
        },
        audience=audience,
    )
    return TokenResponse(
        access_token=token,
        organization_id=membership.organization_id,
        role=Role(membership.role),
        must_change_password=False,
        is_platform_admin=user.is_platform_admin,
    )


@router.post("/forgot-password", status_code=200)
@limiter.limit("10/minute")
def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    request_password_reset(db, email=payload.email)
    db.commit()
    return {"message": PASSWORD_RESET_GENERIC_MESSAGE}


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
@limiter.limit("10/minute")
def reset_password(
    request: Request,
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
) -> Response:
    try:
        reset_password_with_token(db, token=payload.token, new_password=payload.new_password)
    except ValueError as exc:
        code = str(exc)
        if code == "WEAK_PASSWORD":
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters") from exc
        raise HTTPException(status_code=400, detail="This reset link is invalid or expired") from exc
    db.commit()


    return Response(status_code=status.HTTP_204_NO_CONTENT)
@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def change_password(
    payload: ChangePasswordRequest,
    user: User = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
) -> Response:
    if not user.hashed_password or not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.hashed_password = hash_password(payload.new_password)
    user.must_change_password = False
    db.commit()


    return Response(status_code=status.HTTP_204_NO_CONTENT)
@router.get("/me", response_model=UserResponse)
def me(
    user: User = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
    x_organization_id: str | None = Header(default=None, alias="X-Organization-Id"),
    credentials: HTTPAuthorizationCredentials | None = Depends(_me_bearer),
) -> UserResponse:
    organization_id: UUID | None = None
    role: Role | None = None

    token_org_hint: UUID | None = None
    token_aud: str | None = None
    if credentials is not None:
        try:
            payload = decode_access_token(credentials.credentials, audiences=ALL_AUDIENCES)
            token_aud = payload.get("aud")
            if token_aud in TENANT_AUDIENCES and payload.get("organization_id"):
                token_org_hint = parse_optional_uuid(str(payload.get("organization_id")))
        except ValueError:
            token_org_hint = None

    parsed_org_header = parse_optional_uuid(x_organization_id) or token_org_hint
    if parsed_org_header is not None:
        organization_id = parsed_org_header
        membership = (
            db.query(OrganizationMembership)
            .filter(
                OrganizationMembership.user_id == user.id,
                OrganizationMembership.organization_id == organization_id,
            )
            .first()
        )
        if membership and membership.is_active:
            role = Role(membership.role)
        else:
            # Not a member (or inactive): never echo a foreign organization id back.
            organization_id = None
    else:
        platform_role_preview = resolve_platform_role(user)
        if platform_role_preview is None:
            membership = (
                db.query(OrganizationMembership)
                .filter(OrganizationMembership.user_id == user.id, OrganizationMembership.is_active.is_(True))
                .order_by(OrganizationMembership.id.asc())
                .first()
            )
            if membership:
                organization_id = membership.organization_id
                role = Role(membership.role)

    platform_role = resolve_platform_role(user)
    if platform_role is not None and parsed_org_header is None and organization_id is None:
        perms = sorted(platform_permissions_for_role(platform_role))
    else:
        perms = permissions_for_role(role)

    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        organization_id=organization_id,
        role=role,
        is_platform_admin=user.is_platform_admin,
        must_change_password=user.must_change_password,
        permissions=perms,
        platform_role=platform_role.value if platform_role else None,
    )


@router.get("/me/tenant", response_model=UserResponse)
def me_tenant(tenant: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)) -> UserResponse:
    user = db.get(User, tenant.user_id)
    assert user is not None
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        organization_id=tenant.organization_id,
        role=tenant.role,
        is_platform_admin=user.is_platform_admin,
        must_change_password=user.must_change_password,
        permissions=permissions_for_role(tenant.role),
    )
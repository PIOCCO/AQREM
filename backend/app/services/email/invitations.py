"""High-level transactional emails for invitations and verification."""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.services.email import templates
from app.services.email.service import email_delivery_configured, queue_email
from app.services.email.types import OutboundEmail

logger = logging.getLogger("aqrem.email")


def _queue(
    db: Session,
    *,
    email_type: str,
    to_email: str,
    to_name: str | None,
    subject: str,
    html: str,
    text: str,
    organization_id: str | None,
    resource_id: str | None,
    tags: list[str],
) -> bool:
    if not email_delivery_configured():
        logger.info("Email not configured (provider=none); skipped type=%s", email_type)
        return False
    queue_email(
        db,
        OutboundEmail(
            to_email=to_email,
            to_name=to_name,
            subject=subject,
            html=html,
            text=text,
            email_type=email_type,
            tags=tags,
            organization_id=organization_id,
            resource_id=resource_id,
        ),
    )
    return True


def send_admin_invitation_email(
    db: Session,
    *,
    to_email: str,
    invitee_name: str,
    organization_name: str,
    invitation_url: str,
    inviter_label: str,
    expires_at: datetime,
    personal_message: str | None,
    organization_id: str,
    invitation_id: str,
) -> bool:
    expires_label = expires_at.strftime("%d %b %Y %H:%M UTC")
    subject, html, text = templates.admin_invitation_email(
        invitee_name=invitee_name,
        organization_name=organization_name,
        invitation_url=invitation_url,
        inviter_label=inviter_label,
        expires_at_label=expires_label,
        personal_message=personal_message,
    )
    return _queue(
        db,
        email_type="admin_invitation",
        to_email=to_email,
        to_name=invitee_name,
        subject=subject,
        html=html,
        text=text,
        organization_id=organization_id,
        resource_id=invitation_id,
        tags=["admin_invitation"],
    )


def send_member_invitation_email(
    db: Session,
    *,
    to_email: str,
    invitee_name: str,
    organization_name: str,
    invitation_url: str,
    expires_at: datetime,
    organization_id: str,
    invitation_id: str,
) -> bool:
    subject, html, text = templates.member_invitation_email(
        invitee_name=invitee_name,
        organization_name=organization_name,
        invitation_url=invitation_url,
        expires_at_label=expires_at.strftime("%d %b %Y %H:%M UTC"),
    )
    return _queue(
        db,
        email_type="member_invitation",
        to_email=to_email,
        to_name=invitee_name,
        subject=subject,
        html=html,
        text=text,
        organization_id=organization_id,
        resource_id=invitation_id,
        tags=["member_invitation"],
    )


def send_admin_accept_verification_email(
    db: Session,
    *,
    to_email: str,
    organization_name: str,
    organization_id: str,
    invitation_id: str,
    code: str,
) -> bool:
    subject, html, text = templates.verification_code_email(
        organization_name=organization_name,
        purpose="accept your administrator invitation",
        code=code,
    )
    return _queue(
        db,
        email_type="admin_verification_code",
        to_email=to_email,
        to_name=None,
        subject=subject,
        html=html,
        text=text,
        organization_id=organization_id,
        resource_id=invitation_id,
        tags=["verification", "admin_invitation"],
    )


def send_join_verification_email(
    db: Session,
    *,
    to_email: str,
    organization_name: str,
    organization_id: str,
    pending_id: str,
    code: str,
) -> bool:
    subject, html, text = templates.verification_code_email(
        organization_name=organization_name,
        purpose="verify your email for employee join",
        code=code,
    )
    return _queue(
        db,
        email_type="join_verification_code",
        to_email=to_email,
        to_name=None,
        subject=subject,
        html=html,
        text=text,
        organization_id=organization_id,
        resource_id=pending_id,
        tags=["verification", "employee_join"],
    )


def send_password_reset_email(db: Session, *, to_email: str, reset_url: str, user_id: str) -> bool:
    subject, html, text = templates.password_reset_email(reset_url=reset_url)
    return _queue(
        db,
        email_type="password_reset",
        to_email=to_email,
        to_name=None,
        subject=subject,
        html=html,
        text=text,
        organization_id=None,
        resource_id=user_id,
        tags=["password_reset"],
    )


def send_employee_welcome_email(db: Session, *, to_email: str, organization_name: str, organization_id: str) -> bool:
    subject = f"Welcome to {organization_name} on AQREM"
    body = f"<p>Your access to <strong>{organization_name}</strong> is now active.</p>"
    html, _ = templates._layout(title=subject, body_html=body)
    text = f"Welcome to {organization_name} on AQREM.\n"
    return _queue(
        db,
        email_type="employee_welcome",
        to_email=to_email,
        to_name=None,
        subject=subject,
        html=html,
        text=text,
        organization_id=organization_id,
        resource_id=None,
        tags=["employee_welcome"],
    )

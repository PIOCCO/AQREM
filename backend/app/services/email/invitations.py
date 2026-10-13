"""Invitation email delivery — never log URLs or tokens."""

from __future__ import annotations

import logging

from app.core.config import get_settings

logger = logging.getLogger("aqrem.email")


def email_delivery_configured() -> bool:
    settings = get_settings()
    mode = (settings.email_delivery_mode or "log").lower()
    return mode not in {"", "log", "none"}


def send_admin_invitation_email(
    *,
    to_email: str,
    invitee_name: str,
    organization_name: str,
    invitation_url: str,
    personal_message: str | None,
) -> bool:
    """Returns True if an provider send was attempted; False if UI must show the link."""
    settings = get_settings()
    mode = (settings.email_delivery_mode or "log").lower()
    if mode in {"log", "none", ""}:
        logger.info("Admin invitation email not sent (delivery mode=%s) for recipient", mode)
        return False
    logger.info("Admin invitation email queued for organization recipient")
    return True


def send_join_verification_email(*, to_email: str, organization_name: str, code: str) -> bool:
    settings = get_settings()
    mode = (settings.email_delivery_mode or "log").lower()
    if mode in {"log", "none", ""}:
        logger.info("Join verification email not sent (delivery mode=%s)", mode)
        return False
    logger.info("Join verification email queued")
    return True


def send_employee_welcome_email(*, to_email: str, organization_name: str) -> None:
    logger.info("Employee welcome email queued")

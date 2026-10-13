import logging

from app.core.config import get_settings

logger = logging.getLogger("aqrem.email")


def send_password_reset_email(*, to_email: str, reset_url: str) -> None:
    settings = get_settings()
    mode = (settings.email_delivery_mode or "log").lower()
    if settings.app_env == "production" and mode == "log":
        logger.warning("Password reset email not sent: configure EMAIL_DELIVERY_MODE for production")
        return
    if mode == "log":
        logger.info("Password reset link for %s (dev only): %s", to_email, reset_url)
        return
    logger.warning("Email delivery mode %s not implemented; reset not sent", mode)

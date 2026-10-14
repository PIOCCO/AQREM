from app.services.email.invitations import send_password_reset_email as _send_password_reset

__all__ = ["send_password_reset_email"]


def send_password_reset_email(*, db, to_email: str, reset_url: str, user_id: str) -> None:
    _send_password_reset(db, to_email=to_email, reset_url=reset_url, user_id=str(user_id))

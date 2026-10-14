from __future__ import annotations

import logging

import httpx

from app.core.config import Settings
from app.services.email.types import OutboundEmail, SendResult

logger = logging.getLogger("aqrem.email.brevo")

BREVO_SEND_URL = "https://api.brevo.com/v3/smtp/email"


class BrevoProvider:
    name = "brevo"

    def __init__(self, settings: Settings) -> None:
        self._api_key = (settings.brevo_api_key or "").strip()
        self._from_email = settings.email_from_address.strip()
        self._from_name = settings.email_from_name.strip() or "AQREM"
        self._timeout = settings.email_send_timeout_seconds

    def send(self, message: OutboundEmail) -> SendResult:
        if not self._api_key:
            return SendResult(ok=False, error_message="BREVO_API_KEY is not configured")
        if not self._from_email:
            return SendResult(ok=False, error_message="EMAIL_FROM_ADDRESS is not configured")

        payload = {
            "sender": {"name": self._from_name, "email": self._from_email},
            "to": [{"email": message.to_email, "name": message.to_name or message.to_email}],
            "subject": message.subject,
            "htmlContent": message.html,
            "textContent": message.text,
            "tags": message.tags[:10] if message.tags else None,
        }
        headers = {"api-key": self._api_key, "accept": "application/json", "content-type": "application/json"}
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(BREVO_SEND_URL, headers=headers, json=payload)
        except httpx.TimeoutException:
            return SendResult(ok=False, error_message="Brevo request timed out")
        except httpx.HTTPError as exc:
            return SendResult(ok=False, error_message=f"Brevo network error: {type(exc).__name__}")

        if response.status_code >= 500:
            return SendResult(ok=False, error_message=f"Brevo server error ({response.status_code})")
        if response.status_code >= 400:
            detail = response.text[:500] if response.text else response.reason_phrase
            return SendResult(ok=False, error_message=f"Brevo rejected send ({response.status_code}): {detail}")

        message_id = None
        try:
            body = response.json()
            message_id = str(body.get("messageId") or body.get("message_id") or "") or None
        except Exception:
            logger.debug("Brevo response was not JSON")
        return SendResult(ok=True, provider_message_id=message_id)

from __future__ import annotations

import logging

from app.services.email.types import OutboundEmail, SendResult

logger = logging.getLogger("aqrem.email.console")


class ConsoleEmailProvider:
    name = "console"

    def send(self, message: OutboundEmail) -> SendResult:
        logger.info(
            "EMAIL(console) type=%s to=%s subject=%s tags=%s",
            message.email_type,
            message.to_email,
            message.subject,
            ",".join(message.tags) if message.tags else "",
        )
        logger.info("EMAIL(console) text preview: %s", message.text[:400])
        return SendResult(ok=True, provider_message_id="console-local")

from __future__ import annotations

from typing import Protocol

from app.services.email.types import OutboundEmail, SendResult


class EmailProvider(Protocol):
    name: str

    def send(self, message: OutboundEmail) -> SendResult: ...

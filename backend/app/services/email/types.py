from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class OutboundEmail:
    to_email: str
    to_name: str | None
    subject: str
    html: str
    text: str
    email_type: str
    tags: list[str] = field(default_factory=list)
    organization_id: str | None = None
    resource_id: str | None = None


@dataclass
class SendResult:
    ok: bool
    provider_message_id: str | None = None
    error_message: str | None = None

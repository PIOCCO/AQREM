"""Email provider and verification policy tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.email_delivery import EmailDeliveryLog
from app.services.email.service import resolve_email_provider
from app.services.email.types import OutboundEmail, SendResult
from app.services.email.verification_policy import (
    assert_can_send_verification_email,
    generate_six_digit_code,
    hash_verification_code,
)
from app.services.invitations.tokens import tokens_equal


class FakeProvider:
    name = "fake"

    def __init__(self) -> None:
        self.messages: list[OutboundEmail] = []

    def send(self, message: OutboundEmail) -> SendResult:
        self.messages.append(message)
        return SendResult(ok=True, provider_message_id="fake-1")


def test_generate_and_hash_code():
    code = generate_six_digit_code()
    assert len(code) == 6 and code.isdigit()
    digest = hash_verification_code(code)
    assert tokens_equal(digest, code)
    assert not tokens_equal(digest, "000000")


def test_send_rate_limit(db_session: Session):
    db_session.add(
        EmailDeliveryLog(
            email_type="admin_verification_code",
            recipient="a@example.com",
            subject="x",
            status="sent",
            provider="fake",
            created_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()
    with pytest.raises(ValueError, match="RATE_LIMIT_SEND"):
        assert_can_send_verification_email(db_session, recipient="a@example.com", email_type="admin_verification_code")


def test_brevo_provider_builds(monkeypatch):
    settings = Settings(
        app_env="development",
        email_provider="brevo",
        brevo_api_key="test-key",
        email_from_address="noreply@example.com",
    )
    monkeypatch.setattr("app.services.email.service.get_settings", lambda: settings)
    provider = resolve_email_provider(settings)
    assert provider.name == "brevo"

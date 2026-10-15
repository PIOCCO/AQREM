from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from app.auth import configure_auth_cache, verify_api_key
from app.config import Settings
from app.db_health import mark_db_down, mark_db_up
from app.key_cache import KeyValidationCache
from app.limit_cache import LimitEngine, OutageLimits
from app.limits import check_and_consume, configure_engine


@pytest.fixture
def settings() -> Settings:
    return Settings(
        azure_openai_endpoint="https://example.openai.azure.com",
        key_validation_cache_seconds=30,
        key_revoke_max_seconds=30,
        limit_db_stale_seconds=2,
        outage_conservative_rpm=1,
        outage_conservative_tpm=100,
        outage_conservative_monthly_budget=50,
    )


def test_unknown_key_rejected_when_db_down(settings: Settings) -> None:
    configure_auth_cache(settings)
    mark_db_down()
    assert verify_api_key(settings, "gw_unknownkey123456789012345678901234") is None


def test_known_key_works_when_db_down(settings: Settings) -> None:
    configure_auth_cache(settings)
    cache = KeyValidationCache(validation_ttl_seconds=60, revoke_propagation_seconds=60)
    raw = "gw_knownkey123456789012345678901234"
    client = {
        "client_id": "acme",
        "organization_id": "00000000-0000-0000-0000-000000000001",
        "rpm_limit": 100,
        "tpm_limit": 10000,
        "monthly_token_budget": 1000,
    }
    cache.remember_valid(raw, client)
    with patch("app.auth._cache", cache):
        mark_db_down()
        got = verify_api_key(settings, raw)
        assert got and got["client_id"] == "acme"


def test_revoked_key_stops_within_max_seconds(settings: Settings) -> None:
    configure_auth_cache(settings)
    cache = KeyValidationCache(validation_ttl_seconds=60, revoke_propagation_seconds=1)
    raw = "gw_revokekey12345678901234567890123"
    client = {
        "client_id": "acme",
        "organization_id": "00000000-0000-0000-0000-000000000001",
        "rpm_limit": 100,
        "tpm_limit": 10000,
        "monthly_token_budget": 1000,
    }
    cache.remember_valid(raw, client)
    cache.mark_revoked(raw)
    with patch("app.auth._cache", cache):
        mark_db_down()
        assert verify_api_key(settings, raw) is None


def test_degraded_conservative_limits_after_stale(settings: Settings) -> None:
    configure_engine(settings)
    engine = LimitEngine(
        db_stale_seconds=1,
        outage_limits=OutageLimits(rpm=1, tpm=100, monthly_budget=50),
    )
    engine.set_limits("acme", 100, 10000, 1000)
    engine.set_monthly_total("acme", 40)
    engine.mark_db_down()
    time.sleep(1.2)
    assert engine.is_degraded()
    ok, _ = engine.check_local("acme", requests=2, tokens=0)
    assert ok is False


def test_budget_enforced_during_outage_with_stale_cache(settings: Settings) -> None:
    configure_engine(settings)
    from app import limits as limits_mod

    limits_mod._engine.set_limits("acme", 100, 10000, 100)
    limits_mod._engine.set_monthly_total("acme", 95)
    limits_mod._engine.mark_db_down()
    time.sleep(2.5)
    client = {"client_id": "acme"}
    allowed, _, _ = check_and_consume(settings, client, requests=1, tokens=10)
    assert allowed is False

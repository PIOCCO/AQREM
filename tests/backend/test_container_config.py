from __future__ import annotations

import os

import pytest

from app.core.config import Settings
from app.core.container_config import validate_container_startup


def test_api_production_missing_gateway(monkeypatch):
    monkeypatch.setenv("CONTAINER_ROLE", "api")
    monkeypatch.delenv("GATEWAY_URL", raising=False)
    monkeypatch.delenv("GATEWAY_API_KEY", raising=False)
    settings = Settings(
        app_env="production",
        secret_key="x" * 32,
        database_url="postgresql://u:p@localhost/db",
        app_public_base_url="https://acme.example.com",
        azure_storage_connection_string="DefaultEndpointsProtocol=https;AccountName=x;",
        redis_url="redis://localhost:6379/0",
    )
    with pytest.raises(RuntimeError, match="GATEWAY_URL"):
        validate_container_startup("api", settings)


def test_api_production_ok(monkeypatch):
    monkeypatch.setenv("CONTAINER_ROLE", "api")
    monkeypatch.setenv("GATEWAY_URL", "https://gw.example.com")
    monkeypatch.setenv("GATEWAY_API_KEY", "gw_secret")
    settings = Settings(
        app_env="production",
        secret_key="x" * 32,
        database_url="postgresql://u:p@localhost/db",
        app_public_base_url="https://acme.example.com",
        azure_storage_connection_string="DefaultEndpointsProtocol=https;AccountName=x;",
        redis_url="redis://localhost:6379/0",
    )
    validate_container_startup("api", settings)


def test_development_skips_validation():
    settings = Settings(app_env="development")
    validate_container_startup("api", settings)

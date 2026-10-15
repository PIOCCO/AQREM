import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.container_config import validate_container_startup


def test_production_api_requires_gateway(monkeypatch):
    monkeypatch.setenv("CONTAINER_ROLE", "api")
    monkeypatch.delenv("GATEWAY_URL", raising=False)
    monkeypatch.delenv("GATEWAY_API_KEY", raising=False)
    monkeypatch.delenv("LOCAL_PROD_STACK", raising=False)
    with pytest.raises(ValidationError, match="GATEWAY_URL"):
        Settings(
            app_env="production",
            llm_provider="gateway",
            secret_key="x" * 32,
            database_url="postgresql+psycopg://u:p@db/aqrem",
            redis_url="redis://localhost:6379/0",
            azure_storage_connection_string="DefaultEndpointsProtocol=https;AccountName=x",
            app_public_base_url="https://app.example.com",
        )


def test_production_api_passes_with_gateway(monkeypatch):
    monkeypatch.setenv("CONTAINER_ROLE", "api")
    monkeypatch.setenv("GATEWAY_URL", "https://gw.example.com")
    monkeypatch.setenv("GATEWAY_API_KEY", "gw_secret")
    monkeypatch.delenv("LOCAL_PROD_STACK", raising=False)
    settings = Settings(
        app_env="production",
        llm_provider="gateway",
        gateway_url="https://gw.example.com",
        secret_key="x" * 32,
        database_url="postgresql+psycopg://u:p@db/aqrem",
        redis_url="redis://localhost:6379/0",
        azure_storage_connection_string="DefaultEndpointsProtocol=https;AccountName=x",
        app_public_base_url="https://app.example.com",
    )
    validate_container_startup("api", settings)

import pytest
from app.core.config import Settings
from app.core.container_config import validate_container_startup
from pydantic import ValidationError


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


@pytest.mark.parametrize("role", ["api", "worker"])
def test_production_accepts_managed_identity_blob_storage(monkeypatch, role):
    monkeypatch.setenv("CONTAINER_ROLE", role)
    monkeypatch.delenv("LOCAL_PROD_STACK", raising=False)
    settings = Settings(
        _env_file=None,
        app_env="production",
        llm_provider="gateway",
        gateway_url="https://gateway.example.test",
        gateway_api_key="local-test-only-key",
        secret_key="local-test-only-placeholder-signing-key",
        database_url="postgresql+psycopg://test:local-test-only@localhost/test",
        redis_url="redis://localhost:6379/0",
        azure_storage_connection_string=None,
        azure_storage_account_url="https://unit-test.blob.core.windows.net",
        app_public_base_url="https://public.example.test",
    )
    validate_container_startup(role, settings)


@pytest.mark.parametrize("role", ["api", "worker"])
def test_production_still_rejects_missing_blob_storage(monkeypatch, role):
    monkeypatch.setenv("CONTAINER_ROLE", role)
    monkeypatch.delenv("LOCAL_PROD_STACK", raising=False)
    with pytest.raises(ValidationError, match="AZURE_STORAGE"):
        Settings(
            _env_file=None,
            app_env="production",
            llm_provider="gateway",
            gateway_url="https://gateway.example.test",
            gateway_api_key="local-test-only-key",
            secret_key="local-test-only-placeholder-signing-key",
            database_url="postgresql+psycopg://test:local-test-only@localhost/test",
            redis_url="redis://localhost:6379/0",
            azure_storage_connection_string=None,
            azure_storage_account_url=None,
            app_public_base_url="https://public.example.test",
        )

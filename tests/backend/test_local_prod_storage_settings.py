"""Local prod lab stack may use disk storage without Azure blob."""

from __future__ import annotations

import pytest

from app.core.config import Settings


def test_production_still_requires_azure_without_local_prod_flag(monkeypatch):
    monkeypatch.delenv("LOCAL_PROD_STACK", raising=False)
    with pytest.raises(ValueError, match="AZURE_STORAGE_CONNECTION_STRING"):
        Settings(
            app_env="production",
            llm_provider="gateway",
            gateway_url="http://gateway:8080",
            secret_key="x" * 32,
            database_url="postgresql+psycopg://u:p@db/aqrem",
            redis_url="redis://redis:6379/0",
            azure_storage_connection_string="",
        )


def test_local_prod_lab_allows_empty_azure(monkeypatch):
    monkeypatch.setenv("LOCAL_PROD_STACK", "true")
    settings = Settings(
        app_env="production",
        llm_provider="gateway",
        gateway_url="http://gateway:8080",
        secret_key="x" * 32,
        database_url="postgresql+psycopg://u:p@db/aqrem",
        redis_url="redis://redis:6379/0",
        azure_storage_connection_string="",
        local_upload_dir="/data/uploads",
    )
    assert settings.use_azure_blob_storage is False

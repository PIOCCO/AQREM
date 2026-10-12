import pytest

from app.core.config import Settings
from app.core.llm_config import inspect_azure_openai, require_azure_openai


def test_inspect_azure_missing_fields():
    settings = Settings(
        llm_provider="azure",
        azure_openai_endpoint=None,
        azure_openai_api_key=None,
        azure_openai_use_managed_identity=False,
    )
    status = inspect_azure_openai(settings)
    assert not status.configured
    assert "AZURE_OPENAI_ENDPOINT" in status.missing
    assert any("API_KEY" in m or "MANAGED_IDENTITY" in m for m in status.missing)


def test_inspect_azure_api_key_complete():
    settings = Settings(
        llm_provider="azure",
        azure_openai_endpoint="https://example.openai.azure.com",
        azure_openai_api_key="secret-not-logged",
        azure_openai_chat_deployment="aqrem-chat",
        azure_openai_embedding_deployment="aqrem-embed",
    )
    status = inspect_azure_openai(settings)
    assert status.configured
    assert status.auth_mode == "api_key"
    assert status.endpoint_host == "example.openai.azure.com"


def test_require_azure_raises_when_incomplete():
    settings = Settings(llm_provider="azure", azure_openai_endpoint="https://x.openai.azure.com")
    with pytest.raises(RuntimeError, match="Missing"):
        require_azure_openai(settings)


def test_chat_deployment_env_alias():
    settings = Settings.model_validate({"AZURE_OPENAI_DEPLOYMENT": "from-alias"})
    assert settings.azure_openai_chat_deployment == "from-alias"

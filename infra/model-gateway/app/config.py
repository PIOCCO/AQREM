from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    gateway_env: str = "production"
    azure_openai_endpoint: str
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_use_managed_identity: bool = True

    deployment_name_chat: str = Field(default="aqrem-chat", validation_alias="DEPLOYMENT_NAME_CHAT")
    deployment_name_embeddings: str = Field(default="aqrem-embeddings", validation_alias="DEPLOYMENT_NAME_EMBEDDINGS")
    deployment_alias_chat: str = Field(default="chat-default", validation_alias="DEPLOYMENT_ALIAS_CHAT")
    deployment_alias_embeddings: str = Field(default="embeddings-default", validation_alias="DEPLOYMENT_ALIAS_EMBEDDINGS")

    database_url: str | None = None
    database_use_entra: bool = True
    database_host: str | None = None
    database_name: str = "aqrem_control"
    database_user: str | None = None

    max_request_bytes: int = 2_097_152
    upstream_timeout_seconds: float = 120.0

    applicationinsights_connection_string: str | None = None


def get_settings() -> Settings:
    return Settings()

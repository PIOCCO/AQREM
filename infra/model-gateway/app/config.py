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
    internal_provisioning_token: str | None = None
    azure_tenant_id: str | None = Field(default=None, validation_alias="AZURE_TENANT_ID")
    internal_provisioning_audience: str | None = Field(
        default=None, validation_alias="INTERNAL_PROVISIONING_AUDIENCE"
    )
    internal_provisioning_allowed_object_ids: str | None = Field(
        default=None, validation_alias="INTERNAL_PROVISIONING_ALLOWED_OBJECT_IDS"
    )
    trusted_proxy_cidrs: str = Field(
        default="",
        validation_alias="TRUSTED_PROXY_CIDRS",
        description="Only these peers may supply X-Forwarded-For (Container Apps ingress).",
    )
    limit_db_stale_seconds: float = Field(default=120.0, validation_alias="LIMIT_DB_STALE_SECONDS")
    key_validation_cache_seconds: float = Field(default=60.0, validation_alias="KEY_VALIDATION_CACHE_SECONDS")
    key_revoke_max_seconds: float = Field(default=60.0, validation_alias="KEY_REVOKE_MAX_SECONDS")
    outage_conservative_rpm: int = Field(default=10, validation_alias="OUTAGE_CONSERVATIVE_RPM")
    outage_conservative_tpm: int = Field(default=5000, validation_alias="OUTAGE_CONSERVATIVE_TPM")
    outage_conservative_monthly_budget: int = Field(default=100_000, validation_alias="OUTAGE_CONSERVATIVE_MONTHLY_BUDGET")
    internal_allowed_cidrs: str = Field(
        default="10.0.0.0/8,172.16.0.0/12,192.168.0.0/16",
        validation_alias="INTERNAL_ALLOWED_CIDRS",
    )


def get_settings() -> Settings:
    return Settings()

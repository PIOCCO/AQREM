from __future__ import annotations

import os
from functools import lru_cache
from urllib.parse import urlparse

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

def _is_local_prod_lab() -> bool:
    return os.environ.get("LOCAL_PROD_STACK", "").strip().lower() in {"1", "true", "yes"}


_WEAK_SECRET_KEYS = frozenset(
    {
        "dev-secret-change-me",
        "change-me-in-production",
        "changeme",
        "secret",
    }
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Repo-root .env (Docker Compose) then backend/.env overrides when running the lab script
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    secret_key: str = "dev-secret-change-me"
    jwt_issuer: str = Field(default="aqrem", validation_alias=AliasChoices("jwt_issuer", "JWT_ISSUER"))
    password_reset_expire_minutes: int = Field(default=60, validation_alias=AliasChoices("password_reset_expire_minutes", "PASSWORD_RESET_EXPIRE_MINUTES"))
    app_public_base_url: str = Field(
        default="",
        validation_alias=AliasChoices(
            "app_public_base_url",
            "APP_PUBLIC_BASE_URL",
            "PUBLIC_APP_URL",
            "PUBLIC_BASE_URL",
        ),
        description="Public browser URL for invitation links (no trailing slash). Falls back to request Host when unset.",
    )
    email_delivery_mode: str = Field(
        default="log",
        validation_alias=AliasChoices("email_delivery_mode", "EMAIL_DELIVERY_MODE"),
        description="Legacy; prefer EMAIL_PROVIDER (log→console in dev, none in prod)",
    )
    email_provider: str = Field(
        default="",
        validation_alias=AliasChoices("email_provider", "EMAIL_PROVIDER"),
        description="brevo | console (dev only, explicit) | none",
    )
    brevo_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("brevo_api_key", "BREVO_API_KEY"),
    )
    email_from_address: str = Field(
        default="",
        validation_alias=AliasChoices("email_from_address", "EMAIL_FROM_ADDRESS"),
    )
    email_from_name: str = Field(
        default="AQREM",
        validation_alias=AliasChoices("email_from_name", "EMAIL_FROM_NAME"),
    )
    email_send_timeout_seconds: float = Field(default=15.0)
    email_send_max_retries: int = Field(default=2)
    email_send_retry_backoff_seconds: float = Field(default=0.5)
    verification_resend_cooldown_seconds: int = Field(
        default=15,
        ge=5,
        le=300,
        validation_alias=AliasChoices(
            "verification_resend_cooldown_seconds",
            "VERIFICATION_RESEND_COOLDOWN_SECONDS",
        ),
        description="Minimum seconds between invitation verification code emails.",
    )
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    serve_frontend: bool = False
    frontend_dist_path: str | None = None

    database_url: str = "postgresql+psycopg://aqrem:aqrem@localhost:5432/aqrem"
    redis_url: str = "redis://localhost:6379/0"

    azure_storage_connection_string: str | None = None
    azure_storage_container: str = "evidence"
    local_upload_dir: str = "/tmp/aqrem/uploads"

    llm_provider: str = Field(default="mock", validation_alias=AliasChoices("llm_provider", "LLM_PROVIDER"))
    gateway_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("gateway_url", "GATEWAY_URL"),
    )
    gateway_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("gateway_api_key", "GATEWAY_API_KEY"),
    )
    gateway_chat_alias: str = Field(
        default="chat-default",
        validation_alias=AliasChoices("gateway_chat_alias", "GATEWAY_CHAT_ALIAS"),
    )
    gateway_embeddings_alias: str = Field(
        default="embeddings-default",
        validation_alias=AliasChoices("gateway_embeddings_alias", "GATEWAY_EMBEDDINGS_ALIAS"),
    )
    gateway_timeout_seconds: float = Field(
        default=120.0,
        validation_alias=AliasChoices("gateway_timeout_seconds", "GATEWAY_TIMEOUT_SECONDS"),
    )
    azure_openai_endpoint: str | None = Field(
        default=None,
        validation_alias=AliasChoices("azure_openai_endpoint", "AZURE_OPENAI_ENDPOINT"),
    )
    azure_openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("azure_openai_api_key", "AZURE_OPENAI_API_KEY"),
    )
    azure_openai_api_version: str = Field(
        default="2024-10-21",
        validation_alias=AliasChoices("azure_openai_api_version", "AZURE_OPENAI_API_VERSION"),
    )
    azure_openai_use_managed_identity: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "azure_openai_use_managed_identity",
            "AZURE_OPENAI_USE_MANAGED_IDENTITY",
        ),
    )
    azure_openai_embedding_deployment: str = Field(
        default="text-embedding-3-small",
        validation_alias=AliasChoices(
            "azure_openai_embedding_deployment",
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT",
        ),
    )
    azure_openai_chat_deployment: str = Field(
        default="gpt-4o-mini",
        validation_alias=AliasChoices(
            "azure_openai_chat_deployment",
            "AZURE_OPENAI_CHAT_DEPLOYMENT",
            "AZURE_OPENAI_DEPLOYMENT",
        ),
    )
    embedding_dimensions: int = Field(
        default=384,
        validation_alias=AliasChoices("embedding_dimensions", "EMBEDDING_DIMENSIONS"),
    )

    github_app_id: str | None = None
    github_client_id: str | None = None
    github_client_secret: str | None = None
    github_webhook_secret: str | None = None

    max_upload_bytes: int = 52_428_800
    allowed_upload_extensions: str = (
        ".pdf,.docx,.xlsx,.csv,.txt,.md,.json,.yaml,.yml,.zip,.tar.gz"
    )

    default_ignore_patterns: str = (
        "**/node_modules/**,**/dist/**,**/build/**,**/.git/**,"
        "**/__pycache__/**,**/*.pyc,**/.venv/**,**/venv/**,"
        "**/target/**,**/*.min.js,**/*.map"
    )

    access_token_expire_minutes: int = 60 * 24

    cors_allowed_origins: str = Field(
        default="",
        validation_alias=AliasChoices("cors_allowed_origins", "CORS_ALLOWED_ORIGINS"),
    )
    llm_max_question_chars: int = 8_000
    llm_max_evidence_block_chars: int = 2_000
    llm_max_answer_chars: int = 16_000
    llm_max_output_tokens: int = 2_048
    llm_max_retrieval_results: int = 12
    rate_limit_enabled: bool = True
    allow_public_registration: bool = False
    licensing_test_mode: bool = Field(
        default=False,
        validation_alias=AliasChoices("licensing_test_mode", "LICENSING_TEST_MODE"),
    )
    platform_admin_email: str | None = Field(
        default=None,
        validation_alias=AliasChoices("platform_admin_email", "PLATFORM_ADMIN_EMAIL"),
    )
    platform_admin_password: str | None = Field(
        default=None,
        validation_alias=AliasChoices("platform_admin_password", "PLATFORM_ADMIN_PASSWORD"),
    )
    platform_admin_sync_password: bool = Field(
        default=False,
        validation_alias=AliasChoices("platform_admin_sync_password", "PLATFORM_ADMIN_SYNC_PASSWORD"),
        description="When true, reset platform admin password from env on every API startup (dev only).",
    )
    invitation_ttl_hours: int = 72
    audit_retention_days: int = Field(
        default=0,
        validation_alias=AliasChoices("audit_retention_days", "AUDIT_RETENTION_DAYS"),
        description="When > 0, scheduled job deletes audit events older than this many days (except cleanup records).",
    )

    @model_validator(mode="after")
    def _production_guardrails(self) -> Settings:
        if self.app_env == "production":
            object.__setattr__(self, "platform_admin_sync_password", False)
            if self.licensing_test_mode:
                object.__setattr__(self, "licensing_test_mode", False)
            if self.allow_public_registration:
                object.__setattr__(self, "allow_public_registration", False)
            key = self.secret_key.strip()
            if key.lower() in _WEAK_SECRET_KEYS or len(key) < 32:
                raise ValueError(
                    "In production, SECRET_KEY must be a unique value of at least 32 characters."
                )
            if self.llm_provider.lower().strip() == "azure":
                from app.core.llm_config import inspect_azure_openai

                status = inspect_azure_openai(self)
                if not status.configured:
                    raise ValueError(
                        "Production requires complete Azure OpenAI settings when LLM_PROVIDER=azure. "
                        f"Missing: {', '.join(status.missing)}"
                    )
            provider = self.llm_provider.lower().strip()
            if provider in {"mock", "azure"}:
                raise ValueError(
                    "Production requires LLM_PROVIDER=gateway (direct Azure and mock are not allowed)."
                )
            if provider == "gateway":
                from app.core.gateway_config import inspect_gateway

                gw = inspect_gateway(self)
                if not (self.gateway_url or "").strip():
                    raise ValueError(
                        "Production requires GATEWAY_URL when LLM_PROVIDER=gateway. "
                        f"Missing: {', '.join(gw.missing)}"
                    )
            if not (self.azure_storage_connection_string or "").strip() and not _is_local_prod_lab():
                raise ValueError(
                    "Production requires blob storage (AZURE_STORAGE_CONNECTION_STRING); local disk uploads are forbidden."
                )
        return self

    @property
    def use_azure_blob_storage(self) -> bool:
        return bool((self.azure_storage_connection_string or "").strip())

    @property
    def resolved_email_provider(self) -> str:
        explicit = (self.email_provider or "").strip().lower()
        if explicit:
            return explicit
        legacy = (self.email_delivery_mode or "log").strip().lower()
        if legacy in {"log", "console"}:
            return "console" if self.app_env != "production" else "none"
        if legacy in {"none", "disabled", ""}:
            return "none"
        if legacy == "brevo":
            return "brevo"
        return "none"

    @property
    def cors_origins_list(self) -> list[str]:
        origins: list[str] = []
        for part in self.cors_allowed_origins.split(","):
            o = part.strip()
            if o and o not in origins:
                origins.append(o)
        for url in (self.app_public_base_url,):
            parsed = urlparse(url.strip())
            if parsed.scheme in ("http", "https") and parsed.netloc:
                origin = f"{parsed.scheme}://{parsed.netloc}"
                if origin not in origins:
                    origins.append(origin)
        if self.app_env == "development":
            if not origins:
                return ["*"]
            return origins
        return origins

    @property
    def allowed_extensions_set(self) -> set[str]:
        return {ext.strip().lower() for ext in self.allowed_upload_extensions.split(",") if ext.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()

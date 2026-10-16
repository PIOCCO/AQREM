from __future__ import annotations

import os
from functools import lru_cache
from urllib.parse import urlparse

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

def _is_local_prod_lab() -> bool:
    return os.environ.get("LOCAL_PROD_STACK", "").strip().lower() in {"1", "true", "yes"}


def is_local_prod_stack() -> bool:
    """Docker local-prod compose stack (not Azure production)."""
    return _is_local_prod_lab()


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
        # Never echo env values (API keys) inside validation errors.
        hide_input_in_errors=True,
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
    queue_wait_warn_seconds: int = Field(
        default=60,
        ge=10,
        validation_alias=AliasChoices("queue_wait_warn_seconds", "QUEUE_WAIT_WARN_SECONDS"),
    )
    indexing_stale_seconds: int = Field(
        default=120,
        ge=30,
        validation_alias=AliasChoices("indexing_stale_seconds", "INDEXING_STALE_SECONDS"),
    )
    indexing_max_seconds: int = Field(
        default=900,
        ge=60,
        validation_alias=AliasChoices("indexing_max_seconds", "INDEXING_MAX_SECONDS"),
    )
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
    tenant_database_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("tenant_database_url", "TENANT_DATABASE_URL"),
        description="Optional data-plane role (not in aqrem_rls_control) for org-scoped tenant sessions; "
        "defaults to DATABASE_URL.",
    )
    migration_database_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("migration_database_url", "MIGRATION_DATABASE_URL"),
        description="Owner/migration role URL used only for DDL. DATABASE_URL should be the least-privilege app role.",
    )
    run_migrations_on_startup: bool = Field(
        default=True,
        validation_alias=AliasChoices("run_migrations_on_startup", "RUN_MIGRATIONS_ON_STARTUP"),
    )
    database_require_tls: bool | None = Field(
        default=None,
        validation_alias=AliasChoices("database_require_tls", "DATABASE_REQUIRE_TLS"),
        description="Fail the DB check when TLS is not in use. Defaults to true in production.",
    )
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("celery_broker_url", "CELERY_BROKER_URL"),
        description="Overrides REDIS_URL as the Celery broker (e.g. rediss:// private endpoint).",
    )
    key_vault_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("key_vault_url", "KEY_VAULT_URL"),
    )
    azure_storage_account_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("azure_storage_account_url", "AZURE_STORAGE_ACCOUNT_URL"),
        description="https://<acct>.blob.core.windows.net (or private endpoint FQDN); uses managed identity.",
    )
    document_intelligence_endpoint: str | None = Field(
        default=None,
        validation_alias=AliasChoices("document_intelligence_endpoint", "DOCUMENT_INTELLIGENCE_ENDPOINT"),
    )
    document_intelligence_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("document_intelligence_key", "DOCUMENT_INTELLIGENCE_KEY"),
    )
    auth_provider: str = Field(
        default="local",
        validation_alias=AliasChoices("auth_provider", "AUTH_PROVIDER"),
        description="local (email+password). 'entra' is reserved; not implemented yet.",
    )
    license_file: str | None = Field(
        default=None,
        validation_alias=AliasChoices("license_file", "LICENSE_FILE"),
    )
    license_public_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("license_public_key", "LICENSE_PUBLIC_KEY"),
        description="Base64 Ed25519 public key override (tests/key rotation). Default: embedded key.",
    )
    fleet_environments: str = Field(
        default="",
        validation_alias=AliasChoices("fleet_environments", "FLEET_ENVIRONMENTS"),
        description="Comma list name=https://url of dedicated environments for the fleet view.",
    )
    log_format: str = Field(
        default="text",
        validation_alias=AliasChoices("log_format", "LOG_FORMAT"),
        description="text | json",
    )

    azure_storage_connection_string: str | None = None
    azure_storage_container: str = "evidence"
    azure_storage_blob_api_version: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "azure_storage_blob_api_version",
            "AZURE_STORAGE_BLOB_API_VERSION",
        ),
    )
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
    # Azure *deployment* names (what you named the deployment in Azure AI Foundry), not model names.
    azure_openai_embedding_deployment: str = Field(
        default="",
        validation_alias=AliasChoices(
            "azure_openai_embedding_deployment",
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT",
        ),
    )
    azure_openai_embedding_send_dimensions: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "azure_openai_embedding_send_dimensions",
            "AZURE_OPENAI_EMBEDDING_SEND_DIMENSIONS",
        ),
    )
    azure_openai_chat_deployment: str = Field(
        default="",
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
    openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("openai_api_key", "OPENAI_API_KEY"),
    )
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        validation_alias=AliasChoices("openai_base_url", "OPENAI_BASE_URL"),
    )
    openai_chat_model: str = Field(
        default="gpt-4o-mini",
        validation_alias=AliasChoices("openai_chat_model", "OPENAI_CHAT_MODEL"),
    )
    openai_embedding_model: str = Field(
        default="text-embedding-3-small",
        validation_alias=AliasChoices("openai_embedding_model", "OPENAI_EMBEDDING_MODEL"),
    )
    debug_rag: bool = Field(
        default=True,
        validation_alias=AliasChoices("debug_rag", "DEBUG_RAG"),
    )
    product_v1: bool = Field(
        default=True,
        validation_alias=AliasChoices("product_v1", "PRODUCT_V1"),
    )

    github_api_url: str = Field(
        default="https://api.github.com",
        validation_alias=AliasChoices("github_api_url", "GITHUB_API_URL"),
        description="GitHub (Enterprise) API base; only called when a GitHub source is configured.",
    )
    brevo_api_url: str = Field(
        default="https://api.brevo.com/v3/smtp/email",
        validation_alias=AliasChoices("brevo_api_url", "BREVO_API_URL"),
        description="Only called when EMAIL_PROVIDER=brevo.",
    )
    azure_openai_token_scope: str = Field(
        default="https://cognitiveservices.azure.com/.default",
        validation_alias=AliasChoices("azure_openai_token_scope", "AZURE_OPENAI_TOKEN_SCOPE"),
        description="Entra token scope for managed identity (change for sovereign clouds).",
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
    llm_max_output_tokens: int = Field(
        default=1_024,
        validation_alias=AliasChoices("llm_max_output_tokens", "LLM_MAX_ANSWER_TOKENS", "LLM_MAX_OUTPUT_TOKENS"),
    )
    llm_temperature: float = Field(
        default=0.1,
        validation_alias=AliasChoices("llm_temperature", "LLM_TEMPERATURE"),
    )
    azure_openai_reasoning_model: bool = Field(
        default=False,
        validation_alias=AliasChoices("azure_openai_reasoning_model", "AZURE_OPENAI_REASONING_MODEL"),
        description="True for gpt-5*/o-series chat deployments: send max_completion_tokens, omit temperature.",
    )
    azure_openai_reasoning_effort: str = Field(
        default="low",
        validation_alias=AliasChoices("azure_openai_reasoning_effort", "AZURE_OPENAI_REASONING_EFFORT"),
    )
    llm_max_retries: int = Field(
        default=3,
        validation_alias=AliasChoices("llm_max_retries", "LLM_MAX_RETRIES"),
    )
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

    # --- Deployment tier -------------------------------------------------
    deployment_mode: str = Field(
        default="shared",
        validation_alias=AliasChoices("deployment_mode", "DEPLOYMENT_MODE"),
        description="shared (multi-tenant, default) | dedicated (single organization per environment)",
    )
    dedicated_org_name: str = Field(
        default="",
        validation_alias=AliasChoices("dedicated_org_name", "DEDICATED_ORG_NAME"),
    )
    dedicated_org_slug: str = Field(
        default="",
        validation_alias=AliasChoices("dedicated_org_slug", "DEDICATED_ORG_SLUG"),
    )
    setup_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices("setup_token", "SETUP_TOKEN"),
        description="One-time secret required by the dedicated first-admin setup screen.",
    )
    dedicated_support_access: bool = Field(
        default=False,
        validation_alias=AliasChoices("dedicated_support_access", "DEDICATED_SUPPORT_ACCESS"),
        description="Dedicated: allow PLATFORM_SUPPORT/SUPER_ADMIN read-only (GET) access to /api/v1/admin.",
    )
    environment_name: str = Field(
        default="",
        validation_alias=AliasChoices("environment_name", "ENVIRONMENT_NAME"),
    )
    app_version: str = Field(
        default="",
        validation_alias=AliasChoices("app_version", "APP_VERSION"),
    )

    @field_validator("deployment_mode", mode="before")
    @classmethod
    def _norm_mode(cls, v: object) -> object:
        mode = str(v or "shared").strip().lower()
        if mode not in {"shared", "dedicated"}:
            raise ValueError("DEPLOYMENT_MODE must be 'shared' or 'dedicated'")
        return mode

    @property
    def is_dedicated(self) -> bool:
        return self.deployment_mode == "dedicated"

    @field_validator("embedding_dimensions", mode="before")
    @classmethod
    def _blank_dimensions(cls, v: object) -> object:
        # Compose passes EMBEDDING_DIMENSIONS="" when unset; treat as "not configured" (0).
        if isinstance(v, str) and not v.strip():
            return 0
        return v

    @model_validator(mode="after")
    def _production_guardrails(self) -> Settings:
        if self.embedding_dimensions <= 0 and self.llm_provider.lower().strip() in {"mock", "local"}:
            object.__setattr__(self, "embedding_dimensions", 384)
        if self.app_env == "production":
            object.__setattr__(self, "platform_admin_sync_password", False)
            # DEBUG_RAG logs user questions and file names: never in production.
            object.__setattr__(self, "debug_rag", False)
            if self.licensing_test_mode:
                object.__setattr__(self, "licensing_test_mode", False)
            if self.allow_public_registration:
                object.__setattr__(self, "allow_public_registration", False)
            key = self.secret_key.strip()
            if key.lower() in _WEAK_SECRET_KEYS or len(key) < 32:
                raise ValueError(
                    "In production, SECRET_KEY must be a unique value of at least 32 characters."
                )
            provider = self.llm_provider.lower().strip()
            if provider in {"mock", "local", "fake", "test", ""}:
                raise ValueError(
                    "Production refuses to start with a mock or fake LLM provider "
                    f"(LLM_PROVIDER={provider or 'unset'}). "
                    "Set LLM_PROVIDER=azure and fill the AZURE_OPENAI_* values "
                    "(see docs/azure-openai-setup.md). The deterministic local provider is "
                    "allowed only when APP_ENV is not production."
                )
            if provider == "azure":
                from app.core.llm_config import azure_missing_message, inspect_azure_openai

                status = inspect_azure_openai(self)
                if not status.configured:
                    raise ValueError(azure_missing_message(status.missing))
            elif provider == "openai":
                if not (self.openai_api_key or "").strip():
                    raise ValueError(
                        "Production LLM_PROVIDER=openai requires OPENAI_API_KEY. "
                        "Refusing to start with an unconfigured model provider."
                    )
            elif provider == "gateway":
                from app.core.gateway_config import inspect_gateway
                from app.core.llm_config import gateway_points_at_fake

                if gateway_points_at_fake(self):
                    raise ValueError(
                        "Production refuses to start with a mock or fake model provider. "
                        "GATEWAY_URL points at a fake or test upstream."
                    )
                gw = inspect_gateway(self)
                if not (self.gateway_url or "").strip():
                    raise ValueError(
                        "Production requires GATEWAY_URL when LLM_PROVIDER=gateway. "
                        f"Missing: {', '.join(gw.missing)}"
                    )
            else:
                raise ValueError(
                    f"Production refuses unknown LLM_PROVIDER={provider!r}. "
                    "Use azure (recommended), openai, or gateway. Mock providers are not allowed."
                )
            if not self.use_azure_blob_storage and not _is_local_prod_lab():
                raise ValueError(
                    "Production requires blob storage (AZURE_STORAGE_ACCOUNT_URL with managed identity, "
                    "or AZURE_STORAGE_CONNECTION_STRING); local disk uploads are forbidden."
                )
            cs = (self.azure_storage_connection_string or "").lower()
            if not _is_local_prod_lab() and ("devstoreaccount1" in cs or "azurite" in cs or "usedevelopmentstorage" in cs):
                raise ValueError(
                    "Production refuses the Azurite development storage emulator. Configure a real storage account."
                )
        return self

    @property
    def use_azure_blob_storage(self) -> bool:
        return bool((self.azure_storage_connection_string or "").strip() or (self.azure_storage_account_url or "").strip())

    @property
    def broker_url(self) -> str:
        return (self.celery_broker_url or "").strip() or self.redis_url

    @property
    def tls_required_for_db(self) -> bool:
        if self.database_require_tls is not None:
            return self.database_require_tls
        return self.app_env == "production" and not _is_local_prod_lab()

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
    # Optional: pull secrets from Azure Key Vault (managed identity) into the environment
    # before settings are parsed. Values already present in the environment win.
    from app.core.keyvault import load_key_vault_secrets

    load_key_vault_secrets()
    return Settings()

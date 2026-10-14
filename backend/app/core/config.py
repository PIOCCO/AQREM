from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

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
        default="http://127.0.0.1:5173",
        validation_alias=AliasChoices(
            "app_public_base_url",
            "APP_PUBLIC_BASE_URL",
            "PUBLIC_APP_URL",
        ),
        description="Public browser URL for invitation links (no trailing slash). Not derived from Host header.",
    )
    email_delivery_mode: str = Field(
        default="log",
        validation_alias=AliasChoices("email_delivery_mode", "EMAIL_DELIVERY_MODE"),
        description="log (dev only) or disabled until SMTP is configured",
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

    chat_attachment_max_mb: int = Field(
        default=5,
        validation_alias=AliasChoices("chat_attachment_max_mb", "CHAT_ATTACHMENT_MAX_MB"),
    )
    chat_attachment_max_files: int = Field(
        default=3,
        validation_alias=AliasChoices("chat_attachment_max_files", "CHAT_ATTACHMENT_MAX_FILES"),
    )
    chat_attachment_max_total_mb: int = Field(
        default=10,
        validation_alias=AliasChoices("chat_attachment_max_total_mb", "CHAT_ATTACHMENT_MAX_TOTAL_MB"),
    )
    chat_attachment_max_pdf_pages: int = Field(
        default=20,
        validation_alias=AliasChoices("chat_attachment_max_pdf_pages", "CHAT_ATTACHMENT_MAX_PDF_PAGES"),
    )
    chat_attachment_max_text_chars: int = Field(
        default=100_000,
        validation_alias=AliasChoices("chat_attachment_max_text_chars", "CHAT_ATTACHMENT_MAX_TEXT_CHARS"),
    )
    chat_attachment_uploads_per_hour: int = Field(
        default=10,
        validation_alias=AliasChoices("chat_attachment_uploads_per_hour", "CHAT_ATTACHMENT_UPLOADS_PER_HOUR"),
    )
    chat_attachment_max_concurrent_ingestion: int = Field(
        default=4,
        validation_alias=AliasChoices(
            "chat_attachment_max_concurrent_ingestion",
            "CHAT_ATTACHMENT_MAX_CONCURRENT_INGESTION",
        ),
    )
    chat_retrieval_max_chunks: int = Field(
        default=8,
        validation_alias=AliasChoices("chat_retrieval_max_chunks", "CHAT_RETRIEVAL_MAX_CHUNKS"),
    )
    chat_retrieval_max_context_tokens: int = Field(
        default=6000,
        validation_alias=AliasChoices("chat_retrieval_max_context_tokens", "CHAT_RETRIEVAL_MAX_CONTEXT_TOKENS"),
    )

    default_ignore_patterns: str = (
        "**/node_modules/**,**/dist/**,**/build/**,**/.git/**,"
        "**/__pycache__/**,**/*.pyc,**/.venv/**,**/venv/**,"
        "**/target/**,**/*.min.js,**/*.map"
    )

    access_token_expire_minutes: int = 60 * 24

    cors_allowed_origins: str = ""
    llm_max_question_chars: int = 8_000
    llm_max_evidence_block_chars: int = 2_000
    llm_max_answer_chars: int = 16_000
    llm_max_output_tokens: int = 2_048
    llm_max_retrieval_results: int = 12
    rate_limit_enabled: bool = True
    allow_public_registration: bool = False
    licensing_test_mode: bool = Field(
        default=True,
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
        default=True,
        validation_alias=AliasChoices("platform_admin_sync_password", "PLATFORM_ADMIN_SYNC_PASSWORD"),
        description="When true (default in dev), reset platform admin password from env on API startup.",
    )
    invitation_ttl_hours: int = 72

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
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        if self.app_env == "development":
            return ["*"]
        if not self.cors_allowed_origins.strip():
            return []
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @property
    def allowed_extensions_set(self) -> set[str]:
        return {ext.strip().lower() for ext in self.allowed_upload_extensions.split(",") if ext.strip()}

    @property
    def chat_allowed_extensions_set(self) -> set[str]:
        return {".pdf", ".md", ".txt"}

    @property
    def chat_attachment_max_bytes(self) -> int:
        return self.chat_attachment_max_mb * 1024 * 1024

    @property
    def chat_attachment_max_total_bytes(self) -> int:
        return self.chat_attachment_max_total_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()

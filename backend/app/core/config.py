from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Repo-root .env (Docker Compose) then backend/.env overrides when running the lab script
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    secret_key: str = "dev-secret-change-me"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    serve_frontend: bool = False
    frontend_dist_path: str | None = None

    database_url: str = "postgresql+psycopg://aqrem:aqrem@localhost:5432/aqrem"
    redis_url: str = "redis://localhost:6379/0"

    azure_storage_connection_string: str | None = None
    azure_storage_container: str = "evidence"
    local_upload_dir: str = "/tmp/aqrem/uploads"

    llm_provider: str = "mock"
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_use_managed_identity: bool = False
    azure_openai_embedding_deployment: str = "text-embedding-3-small"
    azure_openai_chat_deployment: str = "gpt-4o-mini"
    embedding_dimensions: int = 384

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

    cors_allowed_origins: str = ""
    llm_max_question_chars: int = 8_000
    llm_max_evidence_block_chars: int = 2_000
    llm_max_answer_chars: int = 16_000
    llm_max_output_tokens: int = 2_048
    llm_max_retrieval_results: int = 12
    rate_limit_enabled: bool = True

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


@lru_cache
def get_settings() -> Settings:
    return Settings()

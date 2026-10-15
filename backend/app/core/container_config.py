from __future__ import annotations

import os
from dataclasses import dataclass

from app.core.config import Settings


@dataclass(frozen=True)
class EnvRequirement:
    name: str
    present: bool
    reason: str


def _env_set(name: str) -> bool:
    return bool(os.environ.get(name, "").strip())


def _settings_set(value: str | None) -> bool:
    return bool(value and str(value).strip())


def validate_container_startup(role: str, settings: Settings) -> None:
    """Fail fast in production when required per-client configuration is missing."""
    role = (role or os.environ.get("CONTAINER_ROLE") or "").strip().lower()
    if settings.app_env != "production":
        return
    if os.environ.get("LOCAL_PROD_STACK", "").strip().lower() in {"1", "true", "yes"}:
        return
    if role not in {"api", "worker", "web"}:
        raise RuntimeError(
            f"CONTAINER_ROLE must be api, worker, or web in production (got {role!r})"
        )

    missing: list[str] = []

    if role == "api":
        reqs = [
            EnvRequirement("DATABASE_URL", _settings_set(settings.database_url), "tenant database"),
            EnvRequirement("SECRET_KEY", _settings_set(settings.secret_key), "JWT signing"),
            EnvRequirement(
                "PUBLIC_BASE_URL",
                _settings_set(settings.app_public_base_url),
                "invitation and email links",
            ),
            EnvRequirement("GATEWAY_URL", _env_set("GATEWAY_URL"), "model gateway"),
            EnvRequirement("GATEWAY_API_KEY", _env_set("GATEWAY_API_KEY"), "model gateway auth"),
            EnvRequirement(
                "AZURE_STORAGE_CONNECTION_STRING",
                _settings_set(settings.azure_storage_connection_string),
                "document storage",
            ),
            EnvRequirement("REDIS_URL", _settings_set(settings.redis_url), "task queue broker"),
        ]
        has_cors = _settings_set(settings.cors_allowed_origins) or _settings_set(settings.app_public_base_url)
        if not has_cors:
            missing.append("CORS_ALLOWED_ORIGINS or PUBLIC_BASE_URL (browser API access)")
        for r in reqs:
            if not r.present:
                missing.append(f"{r.name} ({r.reason})")

    elif role == "worker":
        reqs = [
            EnvRequirement("DATABASE_URL", _settings_set(settings.database_url), "tenant database"),
            EnvRequirement("REDIS_URL", _settings_set(settings.redis_url), "Celery broker"),
            EnvRequirement(
                "AZURE_STORAGE_CONNECTION_STRING",
                _settings_set(settings.azure_storage_connection_string),
                "ingestion storage",
            ),
            EnvRequirement("GATEWAY_URL", _env_set("GATEWAY_URL"), "embeddings via gateway"),
            EnvRequirement("GATEWAY_API_KEY", _env_set("GATEWAY_API_KEY"), "model gateway auth"),
        ]
        for r in reqs:
            if not r.present:
                missing.append(f"{r.name} ({r.reason})")

    elif role == "web":
        if not _env_set("VITE_PUBLIC_APP_URL"):
            missing.append("VITE_PUBLIC_APP_URL (build-time; must match PUBLIC_BASE_URL)")

    if missing:
        raise RuntimeError(
            "Production container startup validation failed. Missing: " + "; ".join(missing)
        )

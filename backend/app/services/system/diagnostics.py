"""Diagnostics bundle: versions, dependency checks, config presence, recent errors.

Contains NO secrets (only whether a setting is set) and NO document/chat content.
"""

from __future__ import annotations

import io
import json
import platform
import sys
import time
import zipfile

from app.core.config import Settings, get_settings
from app.core.logging_setup import recent_errors, redact_text

# Settings whose *presence* (not value) is reported.
_PRESENCE = (
    "database_url", "migration_database_url", "redis_url", "celery_broker_url", "key_vault_url",
    "azure_storage_connection_string", "azure_storage_account_url", "azure_openai_endpoint",
    "azure_openai_api_key", "document_intelligence_endpoint", "document_intelligence_key", "setup_token",
    "license_file", "brevo_api_key", "gateway_url", "gateway_api_key", "openai_api_key",
)
# Non-secret values reported verbatim.
_VALUES = (
    "app_env", "deployment_mode", "environment_name", "app_version", "llm_provider", "embedding_dimensions",
    "azure_openai_api_version", "azure_openai_chat_deployment", "azure_openai_embedding_deployment",
    "azure_openai_use_managed_identity", "azure_storage_container", "run_migrations_on_startup",
    "product_v1", "log_format", "auth_provider", "dedicated_support_access", "email_provider",
)


def _packages() -> dict:
    out = {}
    try:
        from importlib.metadata import version

        for name in ("fastapi", "sqlalchemy", "psycopg", "pgvector", "openai", "celery", "azure-storage-blob",
                     "azure-identity", "azure-keyvault-secrets", "cryptography", "pydantic"):
            try:
                out[name] = version(name)
            except Exception:
                out[name] = None
    except Exception:
        pass
    return out


def build_diagnostics(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    from app.db.migrate import LATEST_VERSION
    from app.db.session import engine
    from app.services.system.db_check import run_database_checks
    from app.services.system.health import dependency_report

    db = run_database_checks(settings.database_url, role="app", require_tls=settings.tls_required_for_db, engine=engine)
    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "runtime": {"python": sys.version.split()[0], "platform": platform.platform(), "packages": _packages()},
        "schema_latest_version": LATEST_VERSION,
        "config_values": {k: getattr(settings, k, None) for k in _VALUES},
        "config_present": {k: bool((getattr(settings, k, None) or "").strip()) if isinstance(getattr(settings, k, None), str) or getattr(settings, k, None) is None else True for k in _PRESENCE},
        "dependencies": dependency_report(settings, use_cache=False),
        "database_check": db.to_dict(),
        "recent_errors": [{**e, "msg": redact_text(e.get("msg") or "")} for e in recent_errors.snapshot()],
    }


def diagnostics_zip(settings: Settings | None = None) -> bytes:
    data = build_diagnostics(settings)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("diagnostics.json", json.dumps(data, indent=2, default=str))
        zf.writestr("README.txt", "AQREM diagnostics bundle. Contains versions, dependency status and recent "
                    "error summaries. No secrets or document/chat content are included.\n")
    return buf.getvalue()

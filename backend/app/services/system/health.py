"""Dependency status for /health, /api/v1/version, startup report and diagnostics.

No secrets or document content: only host names, booleans and short error class names.
"""

from __future__ import annotations

import os
import subprocess
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import Settings, get_settings

_CACHE: dict[str, tuple[float, dict]] = {}
_LOCK = threading.Lock()
CACHE_SECONDS = 15


def _host(url: str | None) -> str | None:
    if not url:
        return None
    try:
        p = urlparse(url if "://" in url else f"//{url}")
        return p.hostname
    except Exception:
        return None


def app_version(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    if settings.app_version:
        return settings.app_version
    env = os.environ.get("GIT_COMMIT")
    if env:
        return env
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=Path(__file__).resolve().parents[3],
            stderr=subprocess.DEVNULL, text=True, timeout=2,
        ).strip()
    except Exception:
        return "unknown"


def _check_database(settings: Settings) -> dict:
    from sqlalchemy import text

    from app.db.migrate import LATEST_VERSION, applied_versions
    from app.db.session import engine

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            done = applied_versions(conn)
        current = max(done) if done else 0
        return {"status": "ok" if current >= LATEST_VERSION else "degraded",
                "host": engine.url.host, "schema_version": current, "latest_schema_version": LATEST_VERSION}
    except Exception as exc:
        return {"status": "down", "host": engine.url.host, "error": type(exc).__name__}


def _check_broker(settings: Settings) -> dict:
    url = settings.broker_url
    try:
        import redis

        redis.from_url(url, socket_connect_timeout=2, socket_timeout=2).ping()
        return {"status": "ok", "host": _host(url)}
    except Exception as exc:
        return {"status": "down", "host": _host(url), "error": type(exc).__name__}


def _check_storage(settings: Settings) -> dict:
    if not settings.use_azure_blob_storage:
        from app.services.storage.health import StorageUnavailable, assert_upload_storage_ready

        try:
            assert_upload_storage_ready()
            return {"status": "ok", "kind": "local_disk"}
        except StorageUnavailable:
            return {"status": "down", "kind": "local_disk", "error": "not_writable"}
    host = _host(settings.azure_storage_account_url)
    if not host and settings.azure_storage_connection_string:
        parts = dict(
            p.split("=", 1) for p in settings.azure_storage_connection_string.split(";") if "=" in p
        )
        host = _host(parts.get("BlobEndpoint")) or (
            f"{parts.get('AccountName')}.blob.{parts.get('EndpointSuffix', 'core.windows.net')}"
            if parts.get("AccountName") else None
        )
    try:
        from app.services.storage.factory import get_blob_storage

        storage = get_blob_storage()
        client = getattr(storage, "_container_client", None)
        if client is not None:
            client.get_container_properties()
        return {"status": "ok", "kind": "azure_blob", "host": host,
                "auth": "managed_identity" if settings.azure_storage_account_url and not settings.azure_storage_connection_string else "connection_string"}
    except Exception as exc:
        return {"status": "down", "kind": "azure_blob", "host": host, "error": type(exc).__name__}


def _check_llm(settings: Settings) -> dict:
    from app.core.llm_config import llm_provider_summary

    s = llm_provider_summary(settings)
    endpoint = settings.azure_openai_endpoint if settings.llm_provider == "azure" else (
        settings.gateway_url if settings.llm_provider == "gateway" else (
            settings.openai_base_url if settings.llm_provider == "openai" else None))
    return {"status": "ok" if s.get("configured") else "misconfigured", "provider": s.get("provider"),
            "host": _host(endpoint), "auth": s.get("auth_mode"),
            "chat_model": s.get("chat_model"), "embedding_model": s.get("embedding_model")}


def _check_doc_intel(settings: Settings) -> dict:
    if not settings.document_intelligence_endpoint:
        return {"status": "not_configured"}
    return {"status": "configured", "host": _host(settings.document_intelligence_endpoint)}


def _check_key_vault(settings: Settings) -> dict:
    if not settings.key_vault_url:
        return {"status": "not_configured"}
    from app.core.keyvault import last_report

    return {"status": "error" if last_report.get("error") else "ok", "host": _host(settings.key_vault_url),
            "loaded": list(last_report.get("loaded", [])), "missing": list(last_report.get("missing", []))}


def _check_license(settings: Settings) -> dict:
    if not settings.is_dedicated:
        return {"status": "shared_mode"}
    from app.services.offline_license import license_status_summary

    return license_status_summary(settings)


def dependency_report(settings: Settings | None = None, *, use_cache: bool = True) -> dict:
    settings = settings or get_settings()
    now = time.monotonic()
    with _LOCK:
        cached = _CACHE.get("deps")
        if use_cache and cached and now - cached[0] < CACHE_SECONDS:
            return cached[1]
    deps = {
        "database": _check_database(settings),
        "broker": _check_broker(settings),
        "storage": _check_storage(settings),
        "llm": _check_llm(settings),
        "document_intelligence": _check_doc_intel(settings),
        "key_vault": _check_key_vault(settings),
        "license": _check_license(settings),
    }
    critical = ("database", "storage", "llm")
    bad = [k for k in critical if deps[k]["status"] not in {"ok"}]
    if deps["broker"]["status"] != "ok":
        bad.append("broker")
    report = {
        "status": "ok" if not bad else "degraded",
        "degraded": bad,
        "version": app_version(settings),
        "deployment_mode": settings.deployment_mode,
        "environment": settings.environment_name or settings.app_env,
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "dependencies": deps,
    }
    with _LOCK:
        _CACHE["deps"] = (now, report)
    return report

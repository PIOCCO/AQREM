"""Optional Azure Key Vault secret loader (managed identity).

When KEY_VAULT_URL is set, each known secret is fetched with DefaultAzureCredential
(managed identity in Container Apps, az login locally) and exported to os.environ
*only if the variable is not already set* (explicit env always wins, so local dev and
tests are unaffected). Secret names use dashes: DATABASE_URL -> database-url.

Values are never logged; only names of loaded/missing secrets are.
Container Apps can alternatively use native Key Vault secret references; both work.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger("aqrem.keyvault")

SECRET_ENV_NAMES: tuple[str, ...] = (
    "DATABASE_URL",
    "MIGRATION_DATABASE_URL",
    "REDIS_URL",
    "CELERY_BROKER_URL",
    "SECRET_KEY",
    "SETUP_TOKEN",
    "AZURE_STORAGE_CONNECTION_STRING",
    "AZURE_OPENAI_API_KEY",
    "DOCUMENT_INTELLIGENCE_KEY",
    "OPENAI_API_KEY",
    "GATEWAY_API_KEY",
    "BREVO_API_KEY",
    "GITHUB_CLIENT_SECRET",
    "GITHUB_WEBHOOK_SECRET",
    "PLATFORM_ADMIN_PASSWORD",
    "TENANT_SECRETS_KEY",
    "LICENSE_KEY",
    "APP_DB_PASSWORD",
)

_loaded = False
last_report: dict[str, list[str]] = {"loaded": [], "missing": [], "skipped_env": [], "error": []}


def kv_secret_name(env_name: str) -> str:
    return env_name.lower().replace("_", "-")


def load_key_vault_secrets(*, client=None, force: bool = False) -> dict[str, list[str]]:
    global _loaded
    url = (os.environ.get("KEY_VAULT_URL") or "").strip()
    if not url or (_loaded and not force):
        return last_report
    _loaded = True
    report: dict[str, list[str]] = {"loaded": [], "missing": [], "skipped_env": [], "error": []}
    try:
        if client is None:
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient

            client = SecretClient(vault_url=url, credential=DefaultAzureCredential(exclude_interactive_browser_credential=True))
    except ImportError:
        logger.error("KEY_VAULT_URL set but azure-keyvault-secrets is not installed; using environment only")
        report["error"].append("azure-keyvault-secrets not installed")
        last_report.update(report)
        return report
    for env_name in SECRET_ENV_NAMES:
        if (os.environ.get(env_name) or "").strip():
            report["skipped_env"].append(env_name)
            continue
        try:
            secret = client.get_secret(kv_secret_name(env_name))
            if secret is not None and getattr(secret, "value", None):
                os.environ[env_name] = secret.value
                report["loaded"].append(env_name)
            else:
                report["missing"].append(env_name)
        except Exception as exc:  # ResourceNotFoundError, auth errors, network
            name = type(exc).__name__
            if name == "ResourceNotFoundError":
                report["missing"].append(env_name)
            else:
                report["error"].append(f"{env_name}:{name}")
    logger.info(
        "Key Vault secrets loaded=%s missing=%s errors=%s",
        report["loaded"], report["missing"], report["error"],
    )
    last_report.update(report)
    return report

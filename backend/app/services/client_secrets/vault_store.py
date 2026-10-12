"""Client-owned secret storage (Key Vault in production; in-memory lab adapter)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.core.config import get_settings


class ClientSecretStore(ABC):
    @abstractmethod
    def write_model_token(self, organization_id: UUID, token_value: str) -> str:
        """Persist secret; return vault reference only."""

    @abstractmethod
    def delete_model_token(self, organization_id: UUID) -> None:
        pass

    @abstractmethod
    def test_model_token(self, organization_id: UUID) -> tuple[bool, str]:
        """Return success flag and user-safe message (no secret)."""


class MemoryClientSecretStore(ClientSecretStore):
    """Development-only store — never written to PostgreSQL."""

    _store: dict[str, str] = {}

    def write_model_token(self, organization_id: UUID, token_value: str) -> str:
        key = f"{organization_id}:azure-openai"
        self._store[key] = token_value
        return f"kv://lab/{organization_id}/azure-openai"

    def delete_model_token(self, organization_id: UUID) -> None:
        self._store.pop(f"{organization_id}:azure-openai", None)

    def test_model_token(self, organization_id: UUID) -> tuple[bool, str]:
        if f"{organization_id}:azure-openai" not in self._store:
            return False, "No model token is configured for this organization."
        return True, "Connection test succeeded."


class AzureKeyVaultClientSecretStore(ClientSecretStore):
    """Production adapter — uses managed identity (not available in local lab)."""

    def write_model_token(self, organization_id: UUID, token_value: str) -> str:
        raise RuntimeError(
            "Azure Key Vault write is not configured in this environment. "
            "Set AZURE_KEY_VAULT_URL and managed identity for production."
        )

    def delete_model_token(self, organization_id: UUID) -> None:
        raise RuntimeError("Azure Key Vault is not configured.")

    def test_model_token(self, organization_id: UUID) -> tuple[bool, str]:
        raise RuntimeError("Azure Key Vault is not configured.")


def get_client_secret_store() -> ClientSecretStore:
    settings = get_settings()
    if settings.app_env == "production" and getattr(settings, "azure_key_vault_url", None):
        return AzureKeyVaultClientSecretStore()
    return MemoryClientSecretStore()

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
    def read_model_token(self, organization_id: UUID) -> str | None:
        """Return gateway API key for the organization, if configured."""

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
        key = f"{organization_id}:gateway"
        self._store[key] = token_value
        legacy = f"{organization_id}:azure-openai"
        self._store.pop(legacy, None)
        return f"kv://lab/{organization_id}/gateway"

    def read_model_token(self, organization_id: UUID) -> str | None:
        key = f"{organization_id}:gateway"
        if key in self._store:
            return self._store[key]
        legacy = f"{organization_id}:azure-openai"
        return self._store.get(legacy)

    def delete_model_token(self, organization_id: UUID) -> None:
        self._store.pop(f"{organization_id}:gateway", None)
        self._store.pop(f"{organization_id}:azure-openai", None)

    def test_model_token(self, organization_id: UUID) -> tuple[bool, str]:
        token = self.read_model_token(organization_id)
        if token is None:
            return False, "No model token is configured for this organization."
        settings = get_settings()
        if not (settings.gateway_url or "").strip():
            return False, "Model gateway URL is not configured on this deployment."
        try:
            import httpx

            url = settings.gateway_url.rstrip("/") + "/health/live"
            resp = httpx.get(
                url,
                headers={"Authorization": f"Bearer {token.strip()}"},
                timeout=10.0,
            )
            if resp.status_code == 401:
                return False, "The model token was rejected by the gateway."
            if resp.status_code >= 500:
                return False, "The model gateway is temporarily unavailable."
        except Exception:
            return False, "Could not reach the model gateway. Check the URL and network."
        return True, "Connection test succeeded."


class AzureKeyVaultClientSecretStore(ClientSecretStore):
    """Production adapter — uses managed identity (not available in local lab)."""

    def read_model_token(self, organization_id: UUID) -> str | None:
        raise RuntimeError("Azure Key Vault is not configured.")

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

"""Azure Blob client options (Azurite vs production)."""

from __future__ import annotations

# Stable version supported by common Azurite releases and azure-storage-blob 12.x.
AZURITE_BLOB_API_VERSION = "2024-08-04"


def is_azurite_connection_string(connection_string: str) -> bool:
    lower = connection_string.lower()
    return (
        "devstoreaccount1" in lower
        or ":10000" in lower
        or "azurite" in lower
        or "usedevelopmentstorage=true" in lower.replace(" ", "")
    )


def resolve_blob_api_version(connection_string: str, configured: str | None) -> str | None:
    explicit = (configured or "").strip()
    if explicit:
        return explicit
    if is_azurite_connection_string(connection_string):
        return AZURITE_BLOB_API_VERSION
    return None

"""Strip sensitive or environment-specific keys from source config at rest."""

from __future__ import annotations

from app.schemas.source import redact_source_config

# Keys that must never be set via generic create/update API (use dedicated flows).
_BLOCKED_CONFIG_KEYS = frozenset(
    {
        "github_token",
        "access_token",
        "api_key",
        "password",
        "secret",
        "demo_path",
    }
)


def sanitize_source_config_for_storage(config: dict | None) -> dict:
    """Remove secrets and server-side paths before persisting source.config."""
    if not config:
        return {}
    safe = dict(config)
    for key in list(safe.keys()):
        lower = key.lower()
        if lower in _BLOCKED_CONFIG_KEYS or lower.endswith("_token"):
            safe.pop(key, None)
    return safe


def config_contains_blocked_keys(config: dict | None) -> bool:
    if not config:
        return False
    for key in config:
        lower = key.lower()
        if lower in _BLOCKED_CONFIG_KEYS or lower.endswith("_token"):
            return True
    return False


def public_source_config(config: dict | None) -> dict:
    return redact_source_config(config)

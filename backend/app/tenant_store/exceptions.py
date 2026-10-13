class TenantStoreError(Exception):
    """Base error for tenant data store operations."""


class TenantStoreUnavailable(TenantStoreError):
    """Tenant database is unreachable or circuit is open."""


class TenantSchemaMismatch(TenantStoreError):
    """Tenant schema version incompatible with this application version."""


class TenantHostRejected(TenantStoreError):
    """Host failed SSRF / network policy validation."""

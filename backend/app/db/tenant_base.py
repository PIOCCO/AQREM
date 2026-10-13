from sqlalchemy.orm import DeclarativeBase


class TenantBase(DeclarativeBase):
    """Tenant data-plane ORM metadata (per-company PostgreSQL)."""

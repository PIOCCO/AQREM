"""Per-organization tenant data store configuration (control plane — no secrets)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.control_base import ControlBase


class TenantDataStoreConfig(ControlBase):
    __tablename__ = "tenant_data_store_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    storage_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="managed_colocated")
    connection_method: Mapped[str] = mapped_column(String(32), nullable=False, default="managed")
    host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    database_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    schema_name: Mapped[str] = mapped_column(String(64), nullable=False, default="public")
    ssl_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="verify-full")
    ca_certificate_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    secret_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    multi_host: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_session_attrs: Mapped[str | None] = mapped_column(String(32), nullable=True)
    blob_store_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="managed")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_health_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_health_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_health_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    extra: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

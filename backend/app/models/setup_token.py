"""Dedicated first-run setup: one-time token records and attempt log (control plane, no org scope).

Only a SHA-256 hash of the token is stored, never the token itself.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SetupToken(Base):
    __tablename__ = "setup_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    # "bootstrap" (first start, from SETUP_TOKEN) or "operator_reset" (python -m app.setup reset)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="bootstrap")
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SetupAttempt(Base):
    __tablename__ = "setup_attempts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_ip: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(),
                                                   index=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

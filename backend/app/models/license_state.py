"""Dedicated tier: persisted license runtime state (control plane, single row id=1).

Used for clock-rollback detection (highest time ever observed) and for the grace period
(when a license problem was first detected). Never stores license contents or keys.
"""
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LicenseRuntimeState(Base):
    __tablename__ = "license_runtime_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    highest_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_valid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_license_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    problem_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    problem_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    clock_rollback_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

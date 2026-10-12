"""Startup bootstrap (platform administrator account)."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.organization import User

logger = logging.getLogger("aqrem")


def ensure_platform_admin(db: Session) -> None:
    settings = get_settings()
    email = (settings.platform_admin_email or "").strip().lower()
    password = settings.platform_admin_password
    if not email or not password:
        return

    existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing:
        if not existing.is_platform_admin:
            existing.is_platform_admin = True
            if not existing.hashed_password:
                existing.hashed_password = hash_password(password)
        return

    admin = User(
        email=email,
        full_name="Platform Administrator",
        hashed_password=hash_password(password),
        is_platform_admin=True,
        is_active=True,
        must_change_password=False,
    )
    db.add(admin)
    logger.info("Platform administrator account ensured for %s", email)

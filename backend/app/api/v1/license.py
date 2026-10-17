"""License status (banner) + the dedicated read-only write gate."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.dependencies import get_tenant_context
from app.core.roles import Role, role_at_least
from app.core.tenant import TenantContext
from app.db.session import get_db
from app.services import license_enforcement as le

router = APIRouter()


def license_write_gate(request: Request, db: Session = Depends(get_db)) -> None:
    """Dedicated tier: refuse content-creating writes while the environment is read-only."""
    settings = get_settings()
    if not settings.is_dedicated:
        return
    if le.write_allowed_in_read_only(request.method, request.url.path):
        return
    enf = le.evaluate(db, settings)
    if enf.read_only:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": le.READ_ONLY_CODE, "message": le.MSG_USER_READ_ONLY},
        )


@router.get("/status")
def license_status(tenant: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)) -> dict:
    """Banner data. Administrators get the full explanation; other users only the read-only notice."""
    enf = le.evaluate(db, get_settings())
    return enf.public_dict(admin=role_at_least(tenant.role, Role.ORG_ADMIN))

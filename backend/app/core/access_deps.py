from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_tenant_context
from app.core.tenant import TenantContext
from app.services.access_control.context import UserAccessContext, build_access_context
from app.tenant_store.deps import get_tenant_db


def get_user_access(
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_tenant_db),
) -> UserAccessContext:
    return build_access_context(db, tenant)

from collections.abc import Generator

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_tenant_context
from app.core.tenant import TenantContext
from app.db.session import get_db
from app.tenant_store.exceptions import TenantSchemaMismatch, TenantStoreUnavailable
from app.tenant_store.masking import mask_message
from app.tenant_store.resolver import open_tenant_session


def get_tenant_db(
    tenant: TenantContext = Depends(get_tenant_context),
    control_db: Session = Depends(get_db),
) -> Generator[Session, None, None]:
    try:
        session = open_tenant_session(control_db, tenant.organization_id)
    except TenantSchemaMismatch as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"message": str(exc), "code": "tenant_schema_mismatch"},
        ) from exc
    except TenantStoreUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"message": str(exc), "code": "tenant_store_unavailable"},
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"message": mask_message(str(exc)), "code": "tenant_store_error"},
        ) from exc
    try:
        yield session
    finally:
        session.close()

"""Local-prod stack treats managed PostgreSQL as ready without manual activation."""

from __future__ import annotations

from uuid import uuid4

from app.models.tenant_data_store import TenantDataStoreConfig
from app.services.setup_checklist import tenant_database_setup_complete
from app.tenant_store.resolver import MANAGED_COLOCATED


def test_managed_colocated_ready_on_local_prod_without_validated_at(monkeypatch):
    monkeypatch.setenv("LOCAL_PROD_STACK", "true")
    cfg = TenantDataStoreConfig(
        organization_id=uuid4(),
        storage_mode=MANAGED_COLOCATED,
        connection_method="managed",
        status="active",
        setup_validated_at=None,
    )
    assert tenant_database_setup_complete(cfg) is True


def test_managed_colocated_not_ready_in_real_production_without_validated_at(monkeypatch):
    monkeypatch.delenv("LOCAL_PROD_STACK", raising=False)
    cfg = TenantDataStoreConfig(
        organization_id=uuid4(),
        storage_mode=MANAGED_COLOCATED,
        connection_method="managed",
        status="active",
        setup_validated_at=None,
    )
    assert tenant_database_setup_complete(cfg) is False

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.db.control_base import ControlBase
from app.db.tenant_base import TenantBase
from app.main import create_app
import app.models  # noqa: F401

DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://aqrem:aqrem@localhost:5432/aqrem_test",
)


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(DATABASE_URL, pool_pre_ping=True)
    with eng.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        ControlBase.metadata.drop_all(bind=conn)
        TenantBase.metadata.drop_all(bind=conn)
        ControlBase.metadata.create_all(bind=conn)
        TenantBase.metadata.create_all(bind=conn)
    yield eng
    with eng.begin() as conn:
        ControlBase.metadata.drop_all(bind=conn)
        TenantBase.metadata.drop_all(bind=conn)


@pytest.fixture()
def db_session(engine) -> Generator[Session, None, None]:
    connection = engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(bind=connection, join_transaction_mode="create_savepoint")
    session = SessionLocal()

    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess: Session, trans) -> None:  # noqa: ANN001
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db_session: Session, monkeypatch) -> Generator[TestClient, None, None]:
    from app.services import licensing as licensing_mod

    _real_org_allows_sign_in = licensing_mod.org_allows_sign_in

    def _org_allows_sign_in_for_tests(org, settings=None):
        allowed, reason = _real_org_allows_sign_in(org, settings)
        if allowed:
            return allowed, reason
        from app.core.config import get_settings

        settings = settings or get_settings()
        if settings.app_env != "production" and (org.license_limit or 0) <= 0:
            return True, ""
        return allowed, reason

    monkeypatch.setattr(licensing_mod, "org_allows_sign_in", _org_allows_sign_in_for_tests)
    monkeypatch.setattr("app.core.dependencies.org_allows_sign_in", _org_allows_sign_in_for_tests)

    app = create_app()

    def override_get_db():
        yield db_session

    from app.db.session import get_db
    from app.tenant_store.deps import get_tenant_db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_tenant_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def demo_repo_path() -> str:
    from pathlib import Path

    return str(Path(__file__).resolve().parents[1] / "fixtures" / "demo_saas_repo")

import os
import sys
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

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


def _drop_rls_policies(conn) -> None:
    # RLS policies (migration 3 / test_rls_isolation) reference other tables; drop them before drop_all.
    for t, p in conn.execute(text("SELECT tablename, policyname FROM pg_policies WHERE schemaname='public'")).all():
        conn.execute(text(f'DROP POLICY IF EXISTS "{p}" ON "{t}"'))


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(DATABASE_URL, pool_pre_ping=True)
    with eng.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        _drop_rls_policies(conn)
        ControlBase.metadata.drop_all(bind=conn)
        TenantBase.metadata.drop_all(bind=conn)
        conn.execute(text("DROP TYPE IF EXISTS public_chat_share_index CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS aqrem_schema_versions"))
        ControlBase.metadata.create_all(bind=conn)
        TenantBase.metadata.create_all(bind=conn)
    yield eng
    with eng.begin() as conn:
        _drop_rls_policies(conn)
        ControlBase.metadata.drop_all(bind=conn)
        TenantBase.metadata.drop_all(bind=conn)


@pytest.fixture()
def db_session(engine, monkeypatch) -> Generator[Session, None, None]:
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

    @contextmanager
    def startup_session():
        # Lifespan bootstrap must share the test transaction, just like API requests.
        # Otherwise committed tenants/setup tokens escape rollback into later tests.
        yield session

    monkeypatch.setattr("app.db.session.SessionLocal", startup_session)
    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def production_settings_env(monkeypatch):
    """Synthetic configuration for tests of production guardrails; no cloud calls."""
    monkeypatch.setenv("LLM_PROVIDER", "gateway")
    monkeypatch.setenv("GATEWAY_URL", "https://gateway.example.test")
    monkeypatch.setenv("GATEWAY_API_KEY", "local-test-only-key")
    monkeypatch.setenv("AZURE_STORAGE_ACCOUNT_URL", "https://unit-test.blob.core.windows.net")
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def document_acl_mode(monkeypatch):
    """Exercise the existing group/project ACL mode, separate from PRODUCT_V1."""
    from app.core.config import get_settings

    monkeypatch.setenv("PRODUCT_V1", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def reachable_model_gateway(monkeypatch):
    import httpx
    from app.core.config import get_settings

    monkeypatch.setenv("GATEWAY_URL", "https://gateway.example.test")
    get_settings.cache_clear()

    def gateway_health(url, *, headers, timeout):
        assert url == "https://gateway.example.test/health/live"
        assert headers["Authorization"].startswith("Bearer sk-test-")
        return httpx.Response(200)

    monkeypatch.setattr(httpx, "get", gateway_health)
    yield
    get_settings.cache_clear()


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

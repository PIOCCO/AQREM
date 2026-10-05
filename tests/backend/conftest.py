import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
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
        Base.metadata.drop_all(bind=conn)
        Base.metadata.create_all(bind=conn)
    yield eng
    with eng.begin() as conn:
        Base.metadata.drop_all(bind=conn)


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
def client(db_session: Session) -> Generator[TestClient, None, None]:
    app = create_app()

    def override_get_db():
        yield db_session

    from app.db.session import get_db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def demo_repo_path() -> str:
    from pathlib import Path

    return str(Path(__file__).resolve().parents[1] / "fixtures" / "demo_saas_repo")

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db import rls as _rls  # noqa: F401  (registers SET LOCAL app.current_org hook)

settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)

# Control-plane SQLAlchemy engine (alias kept for existing imports).
control_engine = engine

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

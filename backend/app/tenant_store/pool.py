"""Per-tenant SQLAlchemy engines with circuit breaker."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.tenant_store.exceptions import TenantStoreUnavailable
from app.tenant_store.masking import mask_message

logger = logging.getLogger("aqrem.tenant_pool")

GLOBAL_MAX_ENGINES = 64
POOL_SIZE = 3
MAX_OVERFLOW = 2
STATEMENT_TIMEOUT_MS = 30_000


@dataclass
class CircuitState:
    failures: int = 0
    open_until: float = 0.0


@dataclass
class TenantPoolManager:
    _engines: dict[str, Engine] = field(default_factory=dict)
    _circuits: dict[str, CircuitState] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def get_engine(self, tenant_key: str, url: str) -> Engine:
        now = time.monotonic()
        with self._lock:
            circuit = self._circuits.setdefault(tenant_key, CircuitState())
            if circuit.open_until > now:
                raise TenantStoreUnavailable(
                    "Your company's data store is unreachable. Your administrator has been notified."
                )

            if tenant_key not in self._engines:
                if len(self._engines) >= GLOBAL_MAX_ENGINES:
                    raise TenantStoreUnavailable("Platform connection capacity reached. Retry shortly.")
                safe_log = mask_message(url.split("@")[-1] if "@" in url else tenant_key)
                logger.info("Creating tenant engine for %s target=%s", tenant_key, safe_log)
                self._engines[tenant_key] = create_engine(
                    url,
                    pool_pre_ping=True,
                    pool_size=POOL_SIZE,
                    max_overflow=MAX_OVERFLOW,
                    connect_args={"options": f"-c statement_timeout={STATEMENT_TIMEOUT_MS}"},
                )
            return self._engines[tenant_key]

    def record_failure(self, tenant_key: str) -> None:
        with self._lock:
            circuit = self._circuits.setdefault(tenant_key, CircuitState())
            circuit.failures += 1
            if circuit.failures >= 3:
                circuit.open_until = time.monotonic() + 30.0
                circuit.failures = 0

    def record_success(self, tenant_key: str) -> None:
        with self._lock:
            circuit = self._circuits.setdefault(tenant_key, CircuitState())
            circuit.failures = 0
            circuit.open_until = 0.0

    def session_factory(self, tenant_key: str, url: str) -> sessionmaker:
        engine = self.get_engine(tenant_key, url)
        return sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def dispose_all(self) -> None:
        with self._lock:
            for eng in self._engines.values():
                eng.dispose()
            self._engines.clear()


tenant_pool_manager = TenantPoolManager()

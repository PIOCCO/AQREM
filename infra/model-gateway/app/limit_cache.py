from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, date, datetime


@dataclass
class ClientLimits:
    rpm_limit: int
    tpm_limit: int
    monthly_token_budget: int
    loaded_at: float = field(default_factory=time.time)


@dataclass
class LocalCounters:
    minute_start: datetime
    request_count: int = 0
    token_count: int = 0


class LimitEngine:
    """Per-replica hot path with periodic DB flush. Monthly budget reconciled from DB."""

    def __init__(self, *, flush_interval_seconds: float = 5.0, db_stale_seconds: float = 120.0) -> None:
        self.flush_interval_seconds = flush_interval_seconds
        self.db_stale_seconds = db_stale_seconds
        self._limits: dict[str, ClientLimits] = {}
        self._local: dict[str, LocalCounters] = {}
        self._monthly_cache: dict[str, tuple[int, float]] = {}
        self._db_available = True
        self._db_failed_at: float | None = None
        self._lock = threading.Lock()

    def mark_db_down(self) -> None:
        with self._lock:
            self._db_available = False
            self._db_failed_at = time.time()

    def mark_db_up(self) -> None:
        with self._lock:
            self._db_available = True
            self._db_failed_at = None

    def db_fail_open_allowed(self) -> bool:
        with self._lock:
            if self._db_available:
                return True
            if self._db_failed_at is None:
                return False
            return (time.time() - self._db_failed_at) <= self.db_stale_seconds

    def set_limits(self, client_id: str, rpm: int, tpm: int, budget: int) -> None:
        with self._lock:
            self._limits[client_id] = ClientLimits(rpm, tpm, budget)

    def get_limits(self, client_id: str) -> ClientLimits | None:
        with self._lock:
            return self._limits.get(client_id)

    def check_local(self, client_id: str, *, requests: int = 1, tokens: int = 0) -> tuple[bool, int | None]:
        now = datetime.now(UTC).replace(second=0, microsecond=0)
        with self._lock:
            lim = self._limits.get(client_id)
            if not lim:
                return False, 60
            ctr = self._local.get(client_id)
            if not ctr or ctr.minute_start != now:
                ctr = LocalCounters(minute_start=now)
                self._local[client_id] = ctr
            ctr.request_count += requests
            ctr.token_count += tokens
            if ctr.request_count > lim.rpm_limit:
                return False, 60
            if ctr.token_count > lim.tpm_limit:
                return False, 60
            return True, None

    def set_monthly_total(self, client_id: str, total: int) -> None:
        with self._lock:
            self._monthly_cache[client_id] = (total, time.time())

    def check_monthly_budget(self, client_id: str, add_tokens: int) -> bool:
        with self._lock:
            lim = self._limits.get(client_id)
            if not lim:
                return False
            cached = self._monthly_cache.get(client_id)
            if not cached:
                return True
            total, _ = cached
            return total + add_tokens <= lim.monthly_token_budget

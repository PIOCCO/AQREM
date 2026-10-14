from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime


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


@dataclass
class OutageLimits:
    rpm: int
    tpm: int
    monthly_budget: int


class LimitEngine:
    """Per-replica hot path with periodic DB flush. Monthly budget reconciled from DB."""

    def __init__(
        self,
        *,
        flush_interval_seconds: float = 5.0,
        db_stale_seconds: float = 120.0,
        outage_limits: OutageLimits | None = None,
    ) -> None:
        self.flush_interval_seconds = flush_interval_seconds
        self.db_stale_seconds = db_stale_seconds
        self.outage_limits = outage_limits or OutageLimits(rpm=10, tpm=5000, monthly_budget=100_000)
        self._limits: dict[str, ClientLimits] = {}
        self._local: dict[str, LocalCounters] = {}
        self._monthly_cache: dict[str, tuple[int, float]] = {}
        self._db_available = True
        self._db_failed_at: float | None = None
        self._degraded = False
        self._lock = threading.RLock()

    def mark_db_down(self) -> None:
        with self._lock:
            self._db_available = False
            if self._db_failed_at is None:
                self._db_failed_at = time.time()

    def mark_db_up(self) -> None:
        with self._lock:
            self._db_available = True
            self._db_failed_at = None
            self._degraded = False

    def _update_degraded(self) -> None:
        if self._db_available or self._db_failed_at is None:
            self._degraded = False
            return
        self._degraded = (time.time() - self._db_failed_at) > self.db_stale_seconds

    def is_degraded(self) -> bool:
        with self._lock:
            self._update_degraded()
            return self._degraded

    def db_fail_open_allowed(self) -> bool:
        """Phase 1 outage: serve with last known limits. Phase 2: degraded conservative limits."""
        with self._lock:
            if self._db_available:
                return True
            if self._db_failed_at is None:
                return False
            return True

    def _effective_limits_unlocked(self, client_id: str) -> ClientLimits | None:
        self._update_degraded()
        lim = self._limits.get(client_id)
        if not lim:
            return None
        if not self._degraded:
            return lim
        return ClientLimits(
            rpm_limit=min(lim.rpm_limit, self.outage_limits.rpm),
            tpm_limit=min(lim.tpm_limit, self.outage_limits.tpm),
            monthly_token_budget=min(lim.monthly_token_budget, self.outage_limits.monthly_budget),
            loaded_at=lim.loaded_at,
        )

    def effective_limits(self, client_id: str) -> ClientLimits | None:
        with self._lock:
            return self._effective_limits_unlocked(client_id)

    def set_limits(self, client_id: str, rpm: int, tpm: int, budget: int) -> None:
        with self._lock:
            self._limits[client_id] = ClientLimits(rpm, tpm, budget)

    def get_limits(self, client_id: str) -> ClientLimits | None:
        return self.effective_limits(client_id)

    def check_local(self, client_id: str, *, requests: int = 1, tokens: int = 0) -> tuple[bool, int | None]:
        now = datetime.now(UTC).replace(second=0, microsecond=0)
        with self._lock:
            self._update_degraded()
            lim = self._effective_limits_unlocked(client_id)
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
            self._update_degraded()
            lim = self._effective_limits_unlocked(client_id)
            if not lim:
                return False
            cached = self._monthly_cache.get(client_id)
            if not cached:
                return True
            total, cached_at = cached
            budget_cap = lim.monthly_token_budget
            if self._degraded:
                budget_cap = min(budget_cap, self.outage_limits.monthly_budget)
            return total + add_tokens <= budget_cap

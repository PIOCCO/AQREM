from __future__ import annotations

import threading
import time

_lock = threading.Lock()
_db_available = True
_db_failed_at: float | None = None


def mark_db_up() -> None:
    global _db_available, _db_failed_at
    with _lock:
        _db_available = True
        _db_failed_at = None


def mark_db_down() -> None:
    global _db_available, _db_failed_at
    with _lock:
        _db_available = False
        _db_failed_at = time.time()


def db_is_up() -> bool:
    with _lock:
        return _db_available


def db_down_for_seconds() -> float:
    with _lock:
        if _db_failed_at is None:
            return 0.0
        return time.time() - _db_failed_at

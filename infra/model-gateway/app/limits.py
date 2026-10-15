from __future__ import annotations

from datetime import UTC, date, datetime

from app.config import Settings
from app.db import connection
from app.db_health import mark_db_down, mark_db_up
from app.limit_cache import LimitEngine, OutageLimits

_engine = LimitEngine(flush_interval_seconds=5.0, db_stale_seconds=120.0)


def configure_engine(settings: Settings) -> None:
    global _engine
    _engine = LimitEngine(
        flush_interval_seconds=5.0,
        db_stale_seconds=settings.limit_db_stale_seconds,
        outage_limits=OutageLimits(
            rpm=settings.outage_conservative_rpm,
            tpm=settings.outage_conservative_tpm,
            monthly_budget=settings.outage_conservative_monthly_budget,
        ),
    )


def engine() -> LimitEngine:
    return _engine


def _minute_window(now: datetime | None = None) -> datetime:
    now = now or datetime.now(UTC)
    return now.replace(second=0, microsecond=0, tzinfo=UTC)


def hydrate_client_limits(settings: Settings, client_id: str) -> None:
    try:
        with connection(settings) as conn:
            row = conn.execute(
                """
                SELECT rpm_limit, tpm_limit, monthly_token_budget
                FROM gateway.client WHERE client_id = %s AND active
                """,
                (client_id,),
            ).fetchone()
            if not row:
                return
            _engine.set_limits(
                client_id,
                int(row["rpm_limit"]),
                int(row["tpm_limit"]),
                int(row["monthly_token_budget"]),
            )
            today = date.today()
            usage = conn.execute(
                """
                SELECT COALESCE(SUM(total_tokens), 0) AS t
                FROM gateway.usage_daily
                WHERE client_id = %s AND usage_date >= date_trunc('month', %s::date)
                """,
                (client_id, today),
            ).fetchone()
            _engine.set_monthly_total(client_id, int(usage["t"]))
        mark_db_up()
        _engine.mark_db_up()
    except Exception:
        mark_db_down()
        _engine.mark_db_down()
        raise


def check_and_consume(
    settings: Settings,
    client: dict,
    *,
    requests: int = 1,
    tokens: int = 0,
) -> tuple[bool, int | None, str | None]:
    """Return (allowed, retry_after_seconds, limit_code). limit_code: monthly_budget | rate_limit | db_unavailable."""
    client_id = client["client_id"]
    if _engine.get_limits(client_id) is None:
        hydrate_client_limits(settings, client_id)

    if not _engine.check_monthly_budget(client_id, tokens):
        return False, 3600, "monthly_budget"

    ok, retry = _engine.check_local(client_id, requests=requests, tokens=tokens)
    if not ok:
        return False, retry, "rate_limit"

    try:
        window = _minute_window()
        today = date.today()
        with connection(settings) as conn:
            conn.execute(
                """
                INSERT INTO gateway.rate_window (client_id, window_start, request_count, token_count)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (client_id, window_start) DO UPDATE
                SET request_count = gateway.rate_window.request_count + EXCLUDED.request_count,
                    token_count = gateway.rate_window.token_count + EXCLUDED.token_count
                """,
                (client_id, window, requests, tokens),
            )
        mark_db_up()
        _engine.mark_db_up()
    except Exception:
        mark_db_down()
        _engine.mark_db_down()
        if _engine.db_fail_open_allowed():
            return True, None, None
        return False, 30, "db_unavailable"
    return True, None, None


def record_usage(settings: Settings, client_id: str, prompt_tokens: int, completion_tokens: int) -> None:
    total = prompt_tokens + completion_tokens
    today = date.today()
    try:
        with connection(settings) as conn:
            conn.execute(
                """
                INSERT INTO gateway.usage_daily (client_id, usage_date, prompt_tokens, completion_tokens, total_tokens)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (client_id, usage_date) DO UPDATE SET
                  prompt_tokens = gateway.usage_daily.prompt_tokens + EXCLUDED.prompt_tokens,
                  completion_tokens = gateway.usage_daily.completion_tokens + EXCLUDED.completion_tokens,
                  total_tokens = gateway.usage_daily.total_tokens + EXCLUDED.total_tokens
                """,
                (client_id, today, prompt_tokens, completion_tokens, total),
            )
            usage = conn.execute(
                """
                SELECT COALESCE(SUM(total_tokens), 0) AS t
                FROM gateway.usage_daily
                WHERE client_id = %s AND usage_date >= date_trunc('month', %s::date)
                """,
                (client_id, today),
            ).fetchone()
            _engine.set_monthly_total(client_id, int(usage["t"]))
        mark_db_up()
        _engine.mark_db_up()
    except Exception:
        mark_db_down()
        _engine.mark_db_down()

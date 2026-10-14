from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from app.config import Settings
from app.db import connection


def _minute_window(now: datetime | None = None) -> datetime:
    now = now or datetime.now(UTC)
    return now.replace(second=0, microsecond=0, tzinfo=UTC)


def check_and_consume(
    settings: Settings,
    client: dict,
    *,
    requests: int = 1,
    tokens: int = 0,
) -> tuple[bool, int | None]:
    """Returns (allowed, retry_after_seconds). Uses control-plane DB (no Redis)."""
    client_id = client["client_id"]
    window = _minute_window()
    today = date.today()

    with connection(settings) as conn:
        row = conn.execute(
            """
            SELECT request_count, token_count FROM gateway_rate_window
            WHERE client_id = %s AND window_start = %s
            FOR UPDATE
            """,
            (client_id, window),
        ).fetchone()
        req_count = (row["request_count"] if row else 0) + requests
        tok_count = (row["token_count"] if row else 0) + tokens

        if req_count > client["rpm_limit"]:
            return False, 60
        if tok_count > client["tpm_limit"]:
            return False, 60

        usage = conn.execute(
            """
            SELECT total_tokens FROM gateway_usage_daily
            WHERE client_id = %s AND usage_date = %s
            FOR UPDATE
            """,
            (client_id, today),
        ).fetchone()
        month_total = conn.execute(
            """
            SELECT COALESCE(SUM(total_tokens), 0) AS t
            FROM gateway_usage_daily
            WHERE client_id = %s AND usage_date >= date_trunc('month', %s::date)
            """,
            (client_id, today),
        ).fetchone()["t"]
        if month_total + tokens > client["monthly_token_budget"]:
            return False, 3600

        conn.execute(
            """
            INSERT INTO gateway_rate_window (client_id, window_start, request_count, token_count)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (client_id, window_start) DO UPDATE
            SET request_count = EXCLUDED.request_count, token_count = EXCLUDED.token_count
            """,
            (client_id, window, req_count, tok_count),
        )
    return True, None


def record_usage(settings: Settings, client_id: str, prompt_tokens: int, completion_tokens: int) -> None:
    total = prompt_tokens + completion_tokens
    today = date.today()
    with connection(settings) as conn:
        conn.execute(
            """
            INSERT INTO gateway_usage_daily (client_id, usage_date, prompt_tokens, completion_tokens, total_tokens)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (client_id, usage_date) DO UPDATE SET
              prompt_tokens = gateway_usage_daily.prompt_tokens + EXCLUDED.prompt_tokens,
              completion_tokens = gateway_usage_daily.completion_tokens + EXCLUDED.completion_tokens,
              total_tokens = gateway_usage_daily.total_tokens + EXCLUDED.total_tokens
            """,
            (client_id, today, prompt_tokens, completion_tokens, total),
        )

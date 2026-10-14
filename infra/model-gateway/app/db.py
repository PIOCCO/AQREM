from __future__ import annotations

import contextlib
from collections.abc import Generator
from typing import Any

import psycopg
from azure.identity import DefaultAzureCredential
from psycopg.rows import dict_row

from app.config import Settings

AZURE_PG_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"


def _connect(settings: Settings) -> psycopg.Connection:
    if settings.database_url:
        return psycopg.connect(settings.database_url, row_factory=dict_row)
    if settings.database_use_entra and settings.database_host and settings.database_user:
        token = DefaultAzureCredential().get_token(AZURE_PG_SCOPE).token
        return psycopg.connect(
            host=settings.database_host,
            dbname=settings.database_name,
            user=settings.database_user,
            password=token,
            sslmode="require",
            row_factory=dict_row,
        )
    raise RuntimeError("Database not configured (DATABASE_URL or Entra PG settings required)")


@contextlib.contextmanager
def connection(settings: Settings) -> Generator[psycopg.Connection, None, None]:
    conn = _connect(settings)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def ensure_schema(settings: Settings) -> None:
    ddl = """
    CREATE TABLE IF NOT EXISTS gateway_client (
      client_id TEXT PRIMARY KEY,
      organization_id UUID NOT NULL,
      rpm_limit INT NOT NULL DEFAULT 60,
      tpm_limit INT NOT NULL DEFAULT 60000,
      monthly_token_budget BIGINT NOT NULL DEFAULT 5000000,
      active BOOLEAN NOT NULL DEFAULT TRUE,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE TABLE IF NOT EXISTS gateway_api_key (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      client_id TEXT NOT NULL REFERENCES gateway_client(client_id) ON DELETE CASCADE,
      key_prefix TEXT NOT NULL,
      key_hash BYTEA NOT NULL,
      label TEXT NOT NULL DEFAULT 'primary',
      active BOOLEAN NOT NULL DEFAULT TRUE,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      UNIQUE (client_id, label)
    );
    CREATE TABLE IF NOT EXISTS gateway_usage_daily (
      client_id TEXT NOT NULL,
      usage_date DATE NOT NULL,
      prompt_tokens BIGINT NOT NULL DEFAULT 0,
      completion_tokens BIGINT NOT NULL DEFAULT 0,
      total_tokens BIGINT NOT NULL DEFAULT 0,
      PRIMARY KEY (client_id, usage_date)
    );
    CREATE TABLE IF NOT EXISTS gateway_rate_window (
      client_id TEXT NOT NULL,
      window_start TIMESTAMPTZ NOT NULL,
      request_count INT NOT NULL DEFAULT 0,
      token_count BIGINT NOT NULL DEFAULT 0,
      PRIMARY KEY (client_id, window_start)
    );
    """
    with connection(settings) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
        conn.execute(ddl)

-- Gateway-only tables in isolated schema.

CREATE SCHEMA IF NOT EXISTS gateway;

CREATE TABLE IF NOT EXISTS gateway.client (
  client_id TEXT PRIMARY KEY,
  organization_id UUID NOT NULL,
  rpm_limit INT NOT NULL DEFAULT 60,
  tpm_limit INT NOT NULL DEFAULT 60000,
  monthly_token_budget BIGINT NOT NULL DEFAULT 5000000,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS gateway.api_key (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id TEXT NOT NULL REFERENCES gateway.client(client_id) ON DELETE CASCADE,
  key_prefix TEXT NOT NULL,
  key_hash BYTEA NOT NULL,
  label TEXT NOT NULL DEFAULT 'primary',
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (client_id, label)
);

CREATE TABLE IF NOT EXISTS gateway.usage_daily (
  client_id TEXT NOT NULL REFERENCES gateway.client(client_id) ON DELETE CASCADE,
  usage_date DATE NOT NULL,
  prompt_tokens BIGINT NOT NULL DEFAULT 0,
  completion_tokens BIGINT NOT NULL DEFAULT 0,
  total_tokens BIGINT NOT NULL DEFAULT 0,
  PRIMARY KEY (client_id, usage_date)
);

CREATE TABLE IF NOT EXISTS gateway.rate_window (
  client_id TEXT NOT NULL REFERENCES gateway.client(client_id) ON DELETE CASCADE,
  window_start TIMESTAMPTZ NOT NULL,
  request_count INT NOT NULL DEFAULT 0,
  token_count BIGINT NOT NULL DEFAULT 0,
  PRIMARY KEY (client_id, window_start)
);

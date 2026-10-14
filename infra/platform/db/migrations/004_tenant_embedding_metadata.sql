-- Applied to each tenant PostgreSQL (managed or BYO) during tenant migrations.

CREATE TABLE IF NOT EXISTS tenant_embedding_config (
  id SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  model_name TEXT NOT NULL,
  model_version TEXT NOT NULL,
  deployment_name TEXT NOT NULL,
  dimensions INT NOT NULL,
  indexed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Control-plane schema (platform role only). Gateway role has NO grants here.

CREATE SCHEMA IF NOT EXISTS platform;

CREATE TABLE IF NOT EXISTS platform.cells (
  id TEXT PRIMARY KEY,
  region TEXT NOT NULL,
  environment TEXT NOT NULL,
  core_quota INT NOT NULL,
  cores_used INT NOT NULL DEFAULT 0,
  max_clients INT NOT NULL,
  clients_used INT NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'ACTIVE',
  vnet_id TEXT,
  container_app_environment_id TEXT,
  nat_egress_ip TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS platform.client_deployments (
  deployment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id TEXT NOT NULL UNIQUE,
  organization_id UUID,
  cell_id TEXT REFERENCES platform.cells(id),
  plan TEXT NOT NULL,
  region TEXT NOT NULL,
  db_mode TEXT NOT NULL,
  public_base_url TEXT,
  status TEXT NOT NULL DEFAULT 'PENDING',
  current_step TEXT,
  last_error TEXT,
  terraform_state_key TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT client_deployments_status_check CHECK (
    status IN (
      'PENDING', 'PROVISIONING', 'MIGRATING', 'VERIFYING',
      'ACTIVE', 'FAILED', 'DECOMMISSIONING', 'DECOMMISSIONED'
    )
  )
);

CREATE TABLE IF NOT EXISTS platform.deployment_events (
  id BIGSERIAL PRIMARY KEY,
  deployment_id UUID NOT NULL REFERENCES platform.client_deployments(deployment_id),
  step TEXT NOT NULL,
  outcome TEXT NOT NULL,
  detail TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS platform.audit_log (
  id BIGSERIAL PRIMARY KEY,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  resource_type TEXT NOT NULL,
  resource_id TEXT,
  detail JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_client_deployments_status ON platform.client_deployments(status);
CREATE INDEX IF NOT EXISTS idx_cells_region_env ON platform.cells(region, environment);

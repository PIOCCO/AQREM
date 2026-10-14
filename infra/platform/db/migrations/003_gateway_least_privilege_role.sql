-- Run as bootstrap Entra admin (provisioning SP), NOT as gateway identity.
-- Maps gateway managed identity via: SELECT * FROM pgaadauth_create_principal('<gateway-mi-name>', false, false);

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'aqrem_gateway_app') THEN
    CREATE ROLE aqrem_gateway_app NOLOGIN;
  END IF;
END
$$;

REVOKE ALL ON SCHEMA public FROM aqrem_gateway_app;
REVOKE ALL ON SCHEMA platform FROM aqrem_gateway_app;

GRANT USAGE ON SCHEMA gateway TO aqrem_gateway_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA gateway TO aqrem_gateway_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA gateway TO aqrem_gateway_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA gateway
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO aqrem_gateway_app;

-- After pgaadauth_create_principal for gateway MI:
-- GRANT aqrem_gateway_app TO "<gateway-managed-identity-name>";

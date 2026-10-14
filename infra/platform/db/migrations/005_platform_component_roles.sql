-- Component-scoped DB roles (run as bootstrap Entra admin after 001/002).
-- One role per runtime component; grant only required schemas.

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'aqrem_platform_worker') THEN
    CREATE ROLE aqrem_platform_worker NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'aqrem_product_api') THEN
    CREATE ROLE aqrem_product_api NOLOGIN;
  END IF;
END
$$;

REVOKE ALL ON SCHEMA public FROM aqrem_platform_worker, aqrem_product_api;
REVOKE ALL ON SCHEMA gateway FROM aqrem_platform_worker, aqrem_product_api;

GRANT USAGE ON SCHEMA platform TO aqrem_platform_worker, aqrem_product_api;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA platform TO aqrem_platform_worker;
GRANT SELECT, INSERT ON platform.audit_log TO aqrem_platform_worker;
GRANT SELECT ON ALL TABLES IN SCHEMA platform TO aqrem_product_api;
GRANT INSERT ON platform.audit_log TO aqrem_product_api;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA platform TO aqrem_platform_worker;

ALTER DEFAULT PRIVILEGES IN SCHEMA platform
  GRANT SELECT, INSERT, UPDATE ON TABLES TO aqrem_platform_worker;

-- Map Entra principals after pgaadauth_create_principal('<name>', false, false):
-- GRANT aqrem_gateway_app TO "<gateway-mi-name>";
-- GRANT aqrem_platform_worker TO "<onboarding-worker-sp-name>";
-- GRANT aqrem_product_api TO "<product-api-mi-name>";

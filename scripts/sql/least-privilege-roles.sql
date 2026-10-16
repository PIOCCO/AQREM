-- One-time, idempotent, NON-DESTRUCTIVE switch of an existing AQREM database (e.g. the Pi stack that
-- has been running everything as the superuser "aqrem") to least-privilege roles so row-level
-- security applies. Safe to re-run (refreshes passwords and grants). No data is changed or dropped.
--
--   aqrem_migrator : owns the schema + tables, runs migrations (MIGRATION_DATABASE_URL)
--   aqrem_app      : api / worker / beat control plane (DATABASE_URL); member of aqrem_rls_control
--   aqrem_tenant   : org-scoped data plane (TENANT_DATABASE_URL); no cross-org group
--   aqrem_support  : NOLOGIN; member of aqrem_rls_bypass (enable only for a named support action)
--
-- Run as a superuser while connected to the target database:
--   psql -U aqrem -d aqrem -v dbname=aqrem -v migrator_password=... -v app_password=... \
--        -v tenant_password=... -f scripts/sql/least-privilege-roles.sql
\set ON_ERROR_STOP on

SELECT format('CREATE ROLE %I NOLOGIN', r) FROM unnest(ARRAY['aqrem_migrator','aqrem_app','aqrem_tenant',
  'aqrem_support','aqrem_rls_control','aqrem_rls_bypass']) r
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) \gexec

SELECT format('ALTER ROLE aqrem_migrator LOGIN NOSUPERUSER NOCREATEROLE NOBYPASSRLS PASSWORD %L', :'migrator_password') \gexec
SELECT format('ALTER ROLE aqrem_app      LOGIN NOSUPERUSER NOCREATEROLE NOBYPASSRLS PASSWORD %L', :'app_password') \gexec
SELECT format('ALTER ROLE aqrem_tenant   LOGIN NOSUPERUSER NOCREATEROLE NOBYPASSRLS PASSWORD %L', :'tenant_password') \gexec
ALTER ROLE aqrem_support NOLOGIN NOBYPASSRLS;

GRANT aqrem_rls_bypass, aqrem_rls_control TO aqrem_migrator WITH ADMIN OPTION;
GRANT aqrem_rls_bypass  TO aqrem_support;
GRANT aqrem_rls_control TO aqrem_app;

GRANT CONNECT, CREATE, TEMPORARY ON DATABASE :"dbname" TO aqrem_migrator;
GRANT CONNECT, TEMPORARY ON DATABASE :"dbname" TO aqrem_app, aqrem_tenant, aqrem_support;

CREATE EXTENSION IF NOT EXISTS vector;   -- stays owned by the superuser
ALTER SCHEMA public OWNER TO aqrem_migrator;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO aqrem_app, aqrem_tenant, aqrem_support;

-- Ownership transfer to the migrator (tables carry their owned sequences/row types along).
SELECT format('ALTER TABLE public.%I OWNER TO aqrem_migrator', tablename)
  FROM pg_tables WHERE schemaname = 'public' AND tableowner <> 'aqrem_migrator' \gexec
SELECT format('ALTER SEQUENCE public.%I OWNER TO aqrem_migrator', sequencename)
  FROM pg_sequences WHERE schemaname = 'public' AND sequenceowner <> 'aqrem_migrator' \gexec
SELECT format('ALTER VIEW public.%I OWNER TO aqrem_migrator', viewname)
  FROM pg_views WHERE schemaname = 'public' AND viewowner <> 'aqrem_migrator' \gexec
-- Stand-alone types/functions not belonging to an extension (e.g. enums), skipping pgvector's own.
SELECT format('ALTER TYPE public.%I OWNER TO aqrem_migrator', t.typname)
  FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
 WHERE n.nspname = 'public' AND t.typtype IN ('e', 'd')
   AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = t.oid AND d.deptype = 'e') \gexec
SELECT format('ALTER ROUTINE public.%I(%s) OWNER TO aqrem_migrator', p.proname, pg_get_function_identity_arguments(p.oid))
  FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
 WHERE n.nspname = 'public'
   AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = p.oid AND d.deptype = 'e') \gexec

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO aqrem_app, aqrem_tenant, aqrem_support;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO aqrem_app, aqrem_tenant, aqrem_support;
ALTER DEFAULT PRIVILEGES FOR ROLE aqrem_migrator IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO aqrem_app, aqrem_tenant, aqrem_support;
ALTER DEFAULT PRIVILEGES FOR ROLE aqrem_migrator IN SCHEMA public
  GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO aqrem_app, aqrem_tenant, aqrem_support;

-- Report (no secrets)
SELECT rolname, rolsuper, rolbypassrls, rolcanlogin FROM pg_roles WHERE rolname LIKE 'aqrem%' ORDER BY 1;
SELECT tableowner, count(*) AS tables FROM pg_tables WHERE schemaname = 'public' GROUP BY 1;

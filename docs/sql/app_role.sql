-- AQREM least-privilege roles (run once as the server admin / database owner).
-- Replace the placeholders; generate passwords with e.g. `openssl rand -base64 32`.
-- Works on Azure Database for PostgreSQL Flexible Server and self-managed PostgreSQL 14+.
--
--   aqrem_migrator : owns the schema, runs DDL (MIGRATION_DATABASE_URL). Used only by the migration job.
--   aqrem_app      : runtime role for API + worker (DATABASE_URL). DML only, no DDL, not an owner,
--                    NOBYPASSRLS. Member of aqrem_rls_control (cross-org on identity/control tables only:
--                    login by email, invitations, org creation, super-admin). Tenant data (documents,
--                    chunks, sources, answers, audit, ...) is visible only for app.current_org.
--   aqrem_tenant   : OPTIONAL data-plane role (TENANT_DATABASE_URL). Like aqrem_app but NOT in
--                    aqrem_rls_control: even users/memberships/organizations are limited to the current org.
--   aqrem_support  : created NOLOGIN by migration 3; member of aqrem_rls_bypass (sees all orgs). Enable
--                    only for a named, time-boxed support action:  ALTER ROLE aqrem_support LOGIN PASSWORD '...';
--                    and disable afterwards: ALTER ROLE aqrem_support NOLOGIN;
-- Row-level security groups (created by migration 3; no role uses the BYPASSRLS attribute):
--   aqrem_rls_control (control plane), aqrem_rls_bypass (migrator + aqrem_support only).
--
-- Azure Flexible Server: first allow the extension:  az postgres flexible-server parameter set \
--     --name azure.extensions --value VECTOR --resource-group <rg> --server-name <server>

\set ON_ERROR_STOP on

CREATE ROLE aqrem_migrator LOGIN PASSWORD :'migrator_password';
CREATE ROLE aqrem_app      LOGIN NOBYPASSRLS PASSWORD :'app_password';
CREATE ROLE aqrem_tenant   LOGIN NOBYPASSRLS PASSWORD :'tenant_password';   -- optional
-- RLS groups (migration 3 also creates them idempotently; the migrator needs bypass because FORCE RLS
-- applies to table owners too).
CREATE ROLE aqrem_rls_control NOLOGIN;
CREATE ROLE aqrem_rls_bypass  NOLOGIN;
CREATE ROLE aqrem_support     NOLOGIN NOBYPASSRLS;
GRANT aqrem_rls_bypass  TO aqrem_migrator;
GRANT aqrem_rls_bypass  TO aqrem_support;
GRANT aqrem_rls_control TO aqrem_app;

-- Database (run while connected to the target database, e.g. \c aqrem)
GRANT CONNECT, TEMPORARY ON DATABASE :"dbname" TO aqrem_app, aqrem_tenant, aqrem_support;
GRANT CONNECT, CREATE    ON DATABASE :"dbname" TO aqrem_migrator;

-- pgvector must be created by a role allowed to do so (admin), once:
CREATE EXTENSION IF NOT EXISTS vector;

-- Schema: owned by the migrator; the app can only use it.
CREATE SCHEMA IF NOT EXISTS public;
ALTER SCHEMA public OWNER TO aqrem_migrator;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO aqrem_app, aqrem_tenant, aqrem_support;

-- Existing objects (if the schema was already migrated by another role, transfer ownership first:
--   REASSIGN OWNED BY <old_owner> TO aqrem_migrator;)
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO aqrem_app, aqrem_tenant, aqrem_support;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO aqrem_app, aqrem_tenant, aqrem_support;

-- Future objects created by the migrator are automatically usable by the app.
ALTER DEFAULT PRIVILEGES FOR ROLE aqrem_migrator IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO aqrem_app, aqrem_tenant, aqrem_support;
ALTER DEFAULT PRIVILEGES FOR ROLE aqrem_migrator IN SCHEMA public
  GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO aqrem_app, aqrem_tenant, aqrem_support;

-- Usage:
--   psql "host=... dbname=aqrem user=<admin> sslmode=require" \
--        -v dbname=aqrem -v app_password=... -v tenant_password=... -v migrator_password=... \
--        -f docs/sql/app_role.sql
-- Then:
--   MIGRATION_DATABASE_URL=postgresql+psycopg://aqrem_migrator:...@host:5432/aqrem?sslmode=require
--   DATABASE_URL=postgresql+psycopg://aqrem_app:...@host:5432/aqrem?sslmode=require
--   TENANT_DATABASE_URL=postgresql+psycopg://aqrem_tenant:...@host:5432/aqrem?sslmode=require   # optional
-- Verify: SELECT rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname LIKE 'aqrem%';  (all false
-- except the server admin) and no table is owned by aqrem_app:
--   SELECT tablename FROM pg_tables WHERE schemaname='public' AND tableowner='aqrem_app';  -> 0 rows
--   RUN_MIGRATIONS_ON_STARTUP=false   # and run `python -m app.db.migrate` as a job before rollout

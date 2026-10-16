-- AQREM least-privilege roles (run once as the server admin / database owner).
-- Replace the placeholders; generate passwords with e.g. `openssl rand -base64 32`.
-- Works on Azure Database for PostgreSQL Flexible Server and self-managed PostgreSQL 14+.
--
--   aqrem_migrator : owns the schema, runs DDL (MIGRATION_DATABASE_URL). Used only by the migration job.
--   aqrem_app      : runtime role for API + worker (DATABASE_URL). DML only, no DDL.
--
-- Azure Flexible Server: first allow the extension:  az postgres flexible-server parameter set \
--     --name azure.extensions --value VECTOR --resource-group <rg> --server-name <server>

\set ON_ERROR_STOP on

CREATE ROLE aqrem_migrator LOGIN PASSWORD :'migrator_password';
CREATE ROLE aqrem_app      LOGIN PASSWORD :'app_password';

-- Database (run while connected to the target database, e.g. \c aqrem)
GRANT CONNECT, TEMPORARY ON DATABASE :"dbname" TO aqrem_app;
GRANT CONNECT, CREATE    ON DATABASE :"dbname" TO aqrem_migrator;

-- pgvector must be created by a role allowed to do so (admin), once:
CREATE EXTENSION IF NOT EXISTS vector;

-- Schema: owned by the migrator; the app can only use it.
CREATE SCHEMA IF NOT EXISTS public;
ALTER SCHEMA public OWNER TO aqrem_migrator;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO aqrem_app;

-- Existing objects (if the schema was already migrated by another role, transfer ownership first:
--   REASSIGN OWNED BY <old_owner> TO aqrem_migrator;)
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO aqrem_app;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO aqrem_app;

-- Future objects created by the migrator are automatically usable by the app.
ALTER DEFAULT PRIVILEGES FOR ROLE aqrem_migrator IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO aqrem_app;
ALTER DEFAULT PRIVILEGES FOR ROLE aqrem_migrator IN SCHEMA public
  GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO aqrem_app;

-- Usage:
--   psql "host=... dbname=aqrem user=<admin> sslmode=require" \
--        -v dbname=aqrem -v app_password=... -v migrator_password=... -f docs/sql/app_role.sql
-- Then:
--   MIGRATION_DATABASE_URL=postgresql+psycopg://aqrem_migrator:...@host:5432/aqrem?sslmode=require
--   DATABASE_URL=postgresql+psycopg://aqrem_app:...@host:5432/aqrem?sslmode=require
--   RUN_MIGRATIONS_ON_STARTUP=false   # and run `python -m app.db.migrate` as a job before rollout

-- AQREM tenant data database setup (run as a superuser or database owner).
-- Review with your DBA. Application role does NOT require superuser.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE ROLE aqrem_app LOGIN PASSWORD 'choose-a-strong-password';
CREATE DATABASE aqrem_tenant OWNER aqrem_app;
\c aqrem_tenant

GRANT CONNECT ON DATABASE aqrem_tenant TO aqrem_app;
GRANT USAGE, CREATE ON SCHEMA public TO aqrem_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO aqrem_app;

-- After AQREM runs migrations, aqrem_app needs rights on application tables only.

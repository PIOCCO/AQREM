# Schema migrations

AQREM uses a small versioned, forward-only migration runner (`backend/app/db/migrate.py`),
tracked in table `aqrem_schema_versions`. Per-tenant BYO databases additionally use
`tenant_store/migrations.py` (unchanged).

## Running
* At startup (default, `RUN_MIGRATIONS_ON_STARTUP=true`): the API applies pending migrations under a
  PostgreSQL advisory lock (safe with several replicas). Uses `MIGRATION_DATABASE_URL` if set.
* As a separate job (recommended for dedicated/production, with `RUN_MIGRATIONS_ON_STARTUP=false`):
  `python -m app.db.migrate` (status: `python -m app.db.migrate --status`, exits 1 if pending).
  With `RUN_MIGRATIONS_ON_STARTUP=false` the API refuses to start while migrations are pending and names
  the command to run.

## Policy (enforced by `tests/backend/test_migrations_policy.py`)
* Versions are consecutive integers; never edit or reorder a released migration.
* Additive only: `CREATE ... IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS` (nullable or with default),
  `CREATE INDEX IF NOT EXISTS`. No `DROP TABLE`, `DROP COLUMN`, `TRUNCATE`.
* Removing something takes two releases: release N stops using it, release N+1 (after every
  environment runs N) may drop it in a separately reviewed migration.
* Every migration carries a `rollback_note`.

## Rollback notes per release
| Release | Migrations | Rollback |
|---------|-----------|----------|
| enterprise-tenancy (this branch) | 1 baseline (existing create_all + schema patches, unchanged DDL) | Previous app image works on this schema (no columns removed). The `aqrem_schema_versions` table is ignored by older images. |
| | 2 composite indexes `ix_evidence_items_org_source`, `ix_client_documents_org_created` | Harmless to older images; optional `DROP INDEX IF EXISTS ...`. |
| rls (CHECK 1) | 3 row-level security: group roles `aqrem_rls_control`, `aqrem_rls_bypass`, NOLOGIN `aqrem_support`; `ix_rls_<table>_org` indexes; policies `aqrem_org_isolation` / `aqrem_control_plane` / `aqrem_platform_audit` / `aqrem_bypass`; `ENABLE` + `FORCE ROW LEVEL SECURITY` on the 36 tables in `backend/app/db/rls.py` | **Not transparent to older images** (they never set `app.current_org`, so a non-superuser role sees no tenant rows). See "Rolling back migration 3" below. |

Because migrations are additive, application rollback = redeploy the previous image tag
(exception: migration 3, see the RLS row above).
Database restore from backup is only needed if data written by the new version must be discarded
(see `docs/operations-dedicated.md`).

## Rolling back migration 3 (row-level security)
Tested on a copy of a seeded database (`createdb -T`): before rollback an unscoped query as `aqrem_app`
returned 0 chunks; after `disable` the same older-style query (no `app.current_org`) returned the rows,
vector search worked, and `enable` restored 36/36 tables to ENABLE+FORCE (unscoped query back to 0).

1. Back up first (`pg_dump -Fc`), then, with the migration role:

       MIGRATION_DATABASE_URL=postgresql+psycopg://aqrem_migrator:...@host:5432/aqrem python -m app.db.rls disable

   SQL equivalent (as the table owner `aqrem_migrator` or a superuser), for each table in `ALL_RLS_TABLES`:
   `ALTER TABLE <t> NO FORCE ROW LEVEL SECURITY; ALTER TABLE <t> DISABLE ROW LEVEL SECURITY;`
   Policies, roles and indexes stay; no data changes.
2. Redeploy the older image. **Older images run `create_all`/schema patches with `DATABASE_URL` at startup
   and do not know `MIGRATION_DATABASE_URL`**, so for them point `DATABASE_URL` at the owner role
   (`aqrem_migrator`, or `aqrem` on the Pi) - the least-privilege app role cannot run that DDL.
3. To go forward again: deploy this release (or run `python -m app.db.rls enable`), then
   `python -m app.db.rls status` must report `36/36`.

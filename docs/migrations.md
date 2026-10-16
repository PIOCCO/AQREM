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
| rls (CHECK 1) | 3 row-level security: group roles `aqrem_rls_control`, `aqrem_rls_bypass`, NOLOGIN `aqrem_support`; `ix_rls_<table>_org` indexes; policies `aqrem_org_isolation` / `aqrem_control_plane` / `aqrem_platform_audit` / `aqrem_bypass`; `ENABLE` + `FORCE ROW LEVEL SECURITY` on the tables listed in `backend/app/db/rls.py` | **Not transparent to older images**: images before this release never set `app.current_org`, so with a non-superuser app role they would see no tenant rows. Before redeploying an older image run, as the migration role, for each table in `ALL_RLS_TABLES`: `ALTER TABLE <t> NO FORCE ROW LEVEL SECURITY; ALTER TABLE <t> DISABLE ROW LEVEL SECURITY;` (policies, roles and indexes can stay; no data is changed). Re-enable by re-running migration 3's statements (`python -c "from app.db.migrate import migration_engine; from app.db.rls import apply_rls; e=migration_engine(); c=e.begin().__enter__(); apply_rls(c)"` or simply re-deploying this release with the rows removed from `aqrem_schema_versions` for version 3). |

Because migrations are additive, application rollback = redeploy the previous image tag
(exception: migration 3, see the RLS row above).
Database restore from backup is only needed if data written by the new version must be discarded
(see `docs/operations-dedicated.md`).

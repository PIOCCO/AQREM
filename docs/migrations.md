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

Because migrations are additive, application rollback = redeploy the previous image tag.
Database restore from backup is only needed if data written by the new version must be discarded
(see `docs/operations-dedicated.md`).

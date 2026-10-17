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
| chat guardrails | 4 `organizations.chat_strictness VARCHAR(16) NOT NULL DEFAULT 'balanced'` (additive, `ADD COLUMN IF NOT EXISTS`) | Transparent to older images (they ignore the column). Optional: `ALTER TABLE organizations DROP COLUMN IF EXISTS chat_strictness;` and delete version 4 from `aqrem_schema_versions`. Table is already RLS-covered (control-plane policy). |
| setup hardening (CHECK 3) | 5 tables `setup_tokens` (hash, issued/consumed/revoked), `setup_attempts` (failed/successful attempts); `REVOKE ALL` from `aqrem_tenant`/`aqrem_support` | Older images ignore both tables (they lose the one-time/expiry/lockout guarantees). Optional, separately reviewed: `DROP TABLE setup_attempts, setup_tokens`. |
| schema guard | 6 table `aqrem_schema_guard` (`min_image_schema`, `required_features`), written by every migration run, read-only for runtime roles (re-applied after `ensure_app_role`'s blanket DML grant — fixed in CHECK 6; before, the app role regained write access when the migrate job created it) | Images **from this release on** refuse to start (api, worker, beat, migrator) when the DB requires a newer image. Images built **before** it cannot read the marker; see "Rolling back below a guarded migration". Do not drop. |
| license runtime state (CHECK 6) | 7 table `license_runtime_state` (single row: highest time seen, last valid license, first problem time, clock-rollback flag); app role `SELECT, INSERT, UPDATE` (no `DELETE`), `REVOKE ALL` from `aqrem_tenant`/`aqrem_support` | Older images ignore it and apply their older, stricter license rule (no sign-in without a valid license). Not image-gated. Do not drop: it is the clock-rollback and grace evidence. |

Because migrations are additive, application rollback = redeploy the previous image tag
(exception: migration 3, see the RLS row above).
Database restore from backup is only needed if data written by the new version must be discarded
(see `docs/operations-dedicated.md`).

## Image/schema compatibility guard (migration 6)
Migrations that older images must not run against set `requires_image_feature` (currently 3
`rls_org_isolation`, 5 `setup_tokens_v1`). After each run the migrator writes to `aqrem_schema_guard`:
`min_image_schema` = highest such migration applied (never lowered) and `required_features` (union).
At startup the api, the Celery worker/beat and `python -m app.db.migrate` compare this with the image
(`LATEST_VERSION`, `SUPPORTED_FEATURES`) and **refuse to start** with
`ImageTooOldError: This image (schema N) is older than the database requires (...)` if the image is older
or lacks a feature. An unreadable marker also refuses (fail closed). Runtime roles can only `SELECT` the table.

**Honest limit:** images built before migration 6 do not contain this check and will start anyway. The
guard protects from this release forward; rolling back past it is the manual procedure below.

### Rolling back below a guarded migration
1. Check what the database requires:
   `psql "$MIGRATION_DATABASE_URL" -c "SELECT key, value FROM aqrem_schema_guard"`.
2. Target image schema >= `min_image_schema` and has every `required_features` entry → plain redeploy.
3. Otherwise you are going back past a guarded migration on purpose. For 3 (RLS) follow "Rolling back
   migration 3" below first. For 5 (setup tokens) accept that the old image reads `SETUP_TOKEN` directly
   (no one-time/expiry/lockout) — make sure an admin exists and `SETUP_TOKEN` is unset/rotated.
   Then, as the migration role, lower the marker deliberately and record why:
   `UPDATE aqrem_schema_guard SET value='<target schema>' WHERE key='min_image_schema';`
   `UPDATE aqrem_schema_guard SET value='<features the target supports>' WHERE key='required_features';`
   Images before migration 6 ignore the marker entirely, so for them only step 3's preparation applies.
4. Going forward again, the next migration run raises the marker back.

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

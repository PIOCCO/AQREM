# Tenant embedding model metadata and re-index

Changing the platform embedding deployment forces a **full re-index** for every client.

## Tenant DB table (apply with tenant migrations)

See `infra/platform/db/migrations/004_tenant_embedding_metadata.sql`:

- `embedding_model`, `embedding_model_version`, `embedding_dimensions`, `indexed_at`

On onboard, insert one row matching the platform default deployment.

## Re-index procedure

1. **Freeze ingestion** (pause worker queue processing).
2. Deploy new embedding model / gateway alias target (platform stack).
3. For each tenant:
   - Update `tenant_embedding_config` with new model + dimensions.
   - Truncate or version vector tables (product-specific migration).
   - Enqueue full document re-embed jobs.
4. Run evaluation set (`docs/MODEL_EVAL_RAG.md`) on a pilot tenant.
5. Resume ingestion; monitor gateway TPM and storage egress.

Record completion in platform audit log.

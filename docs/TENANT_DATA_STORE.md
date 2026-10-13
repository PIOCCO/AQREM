# Pluggable tenant data storage (Bring Your Own PostgreSQL)

## Step 0 — Inspection summary

### Control plane tables (always on AQREM `CONTROL_DATABASE_URL`)

| Table | Purpose |
|-------|---------|
| `organizations` | Tenant registry, license |
| `users` | Global identity |
| `organization_memberships` | Roles per org |
| `user_invitations` | Invites |
| `client_environments` | Deployment registry (metadata) |
| `provisioning_jobs` | Provisioning runs |
| `control_plane_events` | Platform events |
| `client_credential_metadata` | Model token **references** (no secret values) |
| `tenant_data_store_configs` | Per-org storage mode, host, secret **reference**, health |

### Tenant data plane tables (per-company PostgreSQL)

| Table | Purpose |
|-------|---------|
| `projects`, `sources`, `source_sync_jobs`, `github_*`, `ingestion_ignore_rules` | Sources |
| `evidence_items`, `evidence_item_versions` | Chunks / vectors |
| `questionnaires`, `questions`, `answers`, `answer_evidence_links` | Questionnaires |
| `answer_library_*`, `answer_staleness_*` | Library / staleness |
| `client_documents` | Upload metadata |
| `audit_events` | **Company** activity log |
| `chat_conversation_shares` | Share tokens |
| `schema_migrations` | Tenant migration version |

### Previously mixed / cross-plane joins

- `Organization` ↔ `Project` ORM relationship (removed; `organization_id` UUID on tenant side only).
- `audit_events.user_id` referenced `users` (FK removed; UUID only).
- `client_documents.source_id` stays **within** tenant DB.
- Platform admin routes query control DB only; tenant APIs use `get_tenant_db`.

### Hard-coded assumptions found (before this feature)

| Assumption | Location |
|------------|----------|
| Single global `DATABASE_URL` | `app/db/session.py` |
| One `Base.metadata.create_all` | `app/main.py` |
| `CREATE EXTENSION vector` at startup | `app/main.py`, tests |
| pgvector `<=>` raw SQL | `retrieval/service.py`, `library/service.py` |
| `to_tsvector('english', …)` | `ingestion/indexer.py` |
| Worker uses global `SessionLocal` | `worker/app/tasks/ingestion.py` |
| Global blob store | `services/storage/factory.py` |
| No versioned Alembic tenant migrations | `schema_patches.py` only |

### Requirements

- PostgreSQL **14–17**, extension **vector** (pgvector) required for full RAG; preflight reports if missing.
- No superuser required for app role (see `docs/sql/tenant_database_setup.sql`).
- TLS: `sslmode=verify-full` default for customer hosts; plaintext rejected.

### Connection methods (honest trade-offs)

| Method | Pros | Cons |
|--------|------|------|
| **Managed by AQREM** | Simplest, backups included | Data in AQREM region |
| **Public + allow-list** | Easy for small IT teams | Latency, exposure surface |
| **Private link / VPN** | Strong network isolation | Setup time, ops burden |
| **Secure connector** (planned) | No inbound holes on-prem | Agent lifecycle |
| **Deploy in customer env** (planned) | Data never leaves VPC | You operate upgrades |

## Architecture

```text
Control DB ──► tenant_data_store_configs (no passwords)
                      │
                      ▼
              TenantStoreResolver ──► pool per tenant ──► Tenant PostgreSQL
                      │
              SecretStore (Key Vault / env in dev)
```

Application code uses `get_tenant_db(tenant)` — never builds DSNs outside the resolver.

## Spec compliance (items 1–10)

| # | Requirement | Status | Proof |
|---|-------------|--------|-------|
| 1 | Storage abstraction + resolver | **Partly** | `tenant_store/resolver.py`, `get_tenant_db`; session-per-tenant (not full repository interface) |
| 2 | Connection methods | **Partly** | `public_tls`, `private_link`, `vpn`, `secure_connector`, `customer_deployed` in config + SSRF; connector/deploy manifests not shipped |
| 3 | Pluggable BlobStore | **Not met** | Global `get_blob_storage()` only |
| 4 | Preflight + setup SQL | **Met** | `tenant_store/preflight.py`, `docs/sql/tenant_database_setup.sql`, org-admin API |
| 5 | Per-tenant migrations | **Partly** | `schema_migrations`, advisory lock, N-1 gate; single forward step today |
| 6 | Pools + circuit breaker + degradation | **Partly** | `tenant_store/pool.py`, 503 + message; chat shows API `detail.message` |
| 7 | Security (SSRF, secrets, masking) | **Partly** | `ssrf.py`, `masking.py`, env secret store; Key Vault/mTLS/rotation UI pending |
| 8 | Admin “Data storage” UI | **Met** | `ClientAdminDataStoragePage`, Playwright `admin-console-nav.spec.ts` |
| 9 | Move / offboarding | **Not met** | Not implemented |
| 10 | Documentation | **Partly** | This doc + SQL script; customer runbooks per method still thin |

### Tests run (this branch)

- `python -m pytest tests/backend` — **134 passed** (includes `test_tenant_data_store.py` SSRF, masking, isolation URL build, org-admin GET storage).
- `npx playwright test e2e/admin-console-nav.spec.ts` — **4 passed** (includes data storage page).

### Not verified here (manual / infra)

- Real PostgreSQL 14–17 matrix in containers (host uses single local PG).
- Cross-tenant isolation with **two separate** database URLs (second test DB).
- On-premises secure connector, VPN, or private link end-to-end.
- Latency benchmarks (managed vs 80 ms simulated link).

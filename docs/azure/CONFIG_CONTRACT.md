# Per-client container configuration contract (Azure)

Set **`CONTAINER_ROLE`** to `api`, `worker`, or `web`. In **`APP_ENV=production`**, startup validation fails fast with a single message listing missing variables.

| Variable | api | worker | web | Purpose | Source |
|----------|:---:|:------:|:---:|---------|--------|
| `CONTAINER_ROLE` | ✓ | ✓ | ✓ | Selects validation set | Pipeline / Container App env |
| `APP_ENV` | ✓ | ✓ | ✓ | `production` enables strict checks | Terraform / pipeline |
| `DATABASE_URL` | ✓ | ✓ | — | Tenant PostgreSQL | Key Vault secret → Container App secret |
| `SECRET_KEY` | ✓ | — | — | JWT signing | Key Vault |
| `PUBLIC_BASE_URL` | ✓ | — | — | Absolute invite/email links (API) | Terraform `public_base_url` |
| `GATEWAY_URL` | ✓ | ✓ | — | Model gateway base URL (Stage 4+) | Platform output → Terraform |
| `GATEWAY_API_KEY` | ✓ | ✓ | — | Per-client gateway key | Client Key Vault → CA secret |
| `AZURE_STORAGE_CONNECTION_STRING` | ✓ | ✓ | — | Document/blob storage | Key Vault (or MI + account name in later stages) |
| `REDIS_URL` | ✓ | ✓ | — | Celery broker (worker queue) | Key Vault / ACA env |
| `CORS_ALLOWED_ORIGINS` | ✓* | — | — | Browser API access | Derived from `PUBLIC_BASE_URL` if unset |
| `VITE_PUBLIC_APP_URL` | — | — | ✓ | Built-in web invite URL base (must match API) | **Build** arg / pipeline |
| `VITE_API_BASE` | — | — | ✓ | Browser → API prefix (often empty behind same host) | Build arg |

\*At least one of `CORS_ALLOWED_ORIGINS` or valid `PUBLIC_BASE_URL` required in production.

## Optional (feature-specific)

| Variable | Containers | Purpose |
|----------|------------|---------|
| `EMAIL_PROVIDER`, `BREVO_API_KEY`, `EMAIL_FROM_ADDRESS` | api | Invitation email |
| `JWT_ISSUER` | api | Token validation |
| `LLM_PROVIDER` | api, worker | `gateway` in Azure (Stage 4 item 2) |

## Startup validation

- **api:** `app.core.container_config.validate_container_startup("api")` in FastAPI lifespan
- **worker:** Celery `worker_process_init` hook
- **web:** build-time — pipeline must set `VITE_PUBLIC_APP_URL`; runtime script `scripts/check_web_build_env.sh` (CI)

## Terraform reference

Client stack today sets on **api**: `GATEWAY_URL`, `GATEWAY_API_KEY` (secret), `PUBLIC_BASE_URL`. Extend pipeline to inject remaining secrets from Key Vault before marking deployment ACTIVE.

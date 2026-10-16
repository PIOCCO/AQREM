# Dedicated (single-tenant) environment stack

One Terraform state per client. Creates, in the AQREM subscription:

* Resource group, VNet (Container Apps / private-endpoint / PostgreSQL subnets), NAT egress — `modules/cell`
* Container Apps environment (VNet-integrated) with `api` (internal), `worker`, `beat`, `redis` (internal TCP), `web` (public HTTPS, proxies `/api` to the api app) and a `migrate` job — `modules/dedicated_env`
* User-assigned managed identity (Key Vault Secrets User, Storage Blob Data Contributor, Cognitive Services OpenAI User, AcrPull)
* Key Vault (RBAC, private endpoint, firewall default deny) with write-only secrets: `secret-key`, `setup-token`, `database-url`, `migration-database-url`, `app-db-password`
* Storage account (no shared keys, no public access, versioning + soft delete) + private endpoint
* PostgreSQL 16 Flexible Server (VNet-injected, TLS required, `azure.extensions=VECTOR`, 35-day backups, zone-redundant HA on `large`) **or** an existing database URL
* Private endpoints to the existing Azure OpenAI / Document Intelligence accounts

Parameters per client: `client`, `location`, `size` (small|medium|large), `db_mode` (new|existing).
Everything else is platform-wide in `platform.auto.tfvars`.

```bash
cp platform.auto.tfvars.example platform.auto.tfvars   # once
scripts/new-client-env.sh contoso westeurope small               # new PostgreSQL
AQREM_EXISTING_DATABASE_URL=... scripts/new-client-env.sh contoso westeurope small --existing-db
scripts/new-client-env.sh contoso westeurope small --validate-only  # offline check
```

Not verified against Azure in this branch (only `fmt`/`init -backend=false`/`validate`). Known follow-ups:
Log Analytics wiring for the Container Apps environment, mirroring `redis:7-alpine` into ACR,
custom domain/Front Door, and private DNS for a BYO database in another network.

# Operating dedicated (single-tenant) environments

Tier selection is a deployment setting: `DEPLOYMENT_MODE=shared` (default, multi-tenant, isolated by
organization) or `DEPLOYMENT_MODE=dedicated` (one organization, own containers, own PostgreSQL).
Same code and images for both.

> Status: the Terraform stack and scripts below pass `terraform fmt`, `init -backend=false` and
> `validate`, and the scripts pass `bash -n` / dry-run. **They have not yet been applied against Azure.**
> Do a first run in a sandbox subscription and fix anything Azure rejects before using them for a client.

## What a dedicated environment contains
See `infra/terraform/stacks/dedicated/README.md`. In short: VNet + NAT, Container Apps environment,
`api` (internal), `worker`, `beat`, `redis` (internal), `web` (public HTTPS), `migrate` job,
Key Vault, Storage, PostgreSQL 16 Flexible Server (or your existing PostgreSQL), private endpoints to
Key Vault, Blob, Azure OpenAI and (optionally) Document Intelligence, and one managed identity.

## Create
Once per platform: `cp infra/terraform/stacks/dedicated/platform.auto.tfvars.example ...platform.auto.tfvars`
and fill in tenant/subscription, registry, image tag, Azure OpenAI account id/endpoint and deployment names.
Mirror `redis:7-alpine` into your ACR. Export `AQREM_TFSTATE_RG` / `AQREM_TFSTATE_ACCOUNT` for remote state.

```bash
az login && az account set -s <subscription>
scripts/new-client-env.sh contoso westeurope small                    # new PostgreSQL
AQREM_EXISTING_DATABASE_URL='postgresql+psycopg://aqrem_app:...@host:5432/aqrem?sslmode=require' \
AQREM_EXISTING_MIGRATION_DATABASE_URL='postgresql+psycopg://aqrem_migrator:...@host:5432/aqrem?sslmode=require' \
  scripts/new-client-env.sh contoso westeurope medium --existing-db     # bring your own PostgreSQL
```
The script plans, asks for confirmation, applies, starts the `migrate` job (which also creates the
least-privilege `aqrem_app` role for a new server) and prints the URL plus how to read the one-time
setup token.

Existing PostgreSQL requirements (checked by **Test database**): PostgreSQL 14–17, TLS, `pgvector`
available (Azure Flexible Server: `azure.extensions=VECTOR`), app role with DML only
(`docs/sql/app_role.sql`), network reachability from the environment's VNet (peering/private endpoint and
DNS are the client's/operator's job; not automated).

Then:
1. Issue a license: `python scripts/aqrem_license.py sign --key <offline private key> --org "Contoso" --seats 50 --expires 2027-10-31 --out contoso.license.json`
2. Store it: `az keyvault secret set --vault-name <kv> -n license-key --file contoso.license.json`
   (the Key Vault firewall only admits `deployer_ip_cidrs`), then restart the api revision.
3. Give the client admin the URL and the setup token
   (`az keyvault secret show --vault-name <kv> -n setup-token --query value -o tsv`). They open `/setup`,
   create the first administrator, and sign in. The platform console is disabled in dedicated mode
   (`DEDICATED_SUPPORT_ACCESS=true` re-enables read-only GET access for platform staff).
4. Add the environment to the fleet list of the platform console: `FLEET_ENVIRONMENTS=contoso=https://<web-fqdn>,...`.

## Update / roll out
```bash
scripts/rollout-dedicated.sh 2026.11.0 contoso --registry acraqrem.azurecr.io   # one environment
scripts/rollout-dedicated.sh 2026.11.0 all     --registry acraqrem.azurecr.io   # every RG tagged tier=dedicated
scripts/rollout-dedicated.sh 2026.11.0 contoso --registry ... --dry-run         # print the az commands
```
Order per environment: migrate job with the new image → wait for success → api/worker/beat/web →
verify `/api/v1/version` reports the tag → print `/health`. A failed migration stops that environment
before any app is touched. Afterwards set `image_tag` in `platform.auto.tfvars` so Terraform agrees.
Suggested practice: roll out to one canary client, watch the Fleet page, then `all`.

## Roll back
Migrations are forward-only and additive (`docs/migrations.md`), so the previous image runs on the newer
schema: `scripts/rollout-dedicated.sh <previous-tag> <client|all>`. Alternatively re-activate the
previous Container Apps revision (`az containerapp revision activate`). Restore the database only if data
written by the new version must be discarded (below).

## Backup
* PostgreSQL Flexible Server: automatic backups, 35-day retention, point-in-time restore (configured by the
  stack). Geo-redundant backup is off by default (data residency); enable in the module if required.
* Blob storage: versioning + 14-day soft delete for blobs and containers. For longer retention add an
  Azure Backup vault policy for blobs (not automated here).
* Key Vault: soft delete 90 days + purge protection.
* Bring-your-own PostgreSQL: backups are the database owner's responsibility.

## Restore
* Database to a point in time:
  `az postgres flexible-server restore -g rg-aqrem-<client> -n <new-server> --source-server <server> --restore-time <ISO8601>`,
  then update the Key Vault secrets `database-url` / `migration-database-url` to the new host (or swap DNS)
  and restart the apps. Run the `migrate` job afterwards (no-op if already current).
* Blobs: restore a previous version or undelete in the portal/CLI (`az storage blob undelete`).
* Verify with **Test database** and **Download diagnostics** in the org-admin console.

## Delete
1. Export anything the client wants (documents are their own uploads; audit log export: org-admin → Audit → Export).
2. `cd infra/terraform/clients/<client> && terraform destroy` (same variables as create).
   Key Vault stays soft-deleted for 90 days with purge protection (by design). The PostgreSQL server's
   backups are deleted with the server; take a final `pg_dump` first if contractually required.
3. Remove the environment from `FLEET_ENVIRONMENTS` and revoke/expire its license.

## Health and diagnostics
* `GET /health` — always 200 while serving; body lists database (incl. schema version), broker, storage,
  LLM, Document Intelligence, Key Vault, license status. `GET /health/ready` returns 503 when degraded.
* `GET /api/v1/version` — version, mode, schema version (used by the Fleet page).
* Startup log prints one line per dependency and the database checks (TLS, pgvector, permissions).
* Org admin (dedicated) → Setup page → **Test database** / **Download diagnostics** (zip without secrets or content).

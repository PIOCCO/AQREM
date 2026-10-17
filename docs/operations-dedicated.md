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
   create the first administrator, and sign in. Read **First-run setup security** below first: by
   default `/setup` is not reachable from the internet. The platform console is disabled in dedicated mode
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

## First-run setup security (`/setup`)
The setup screen creates the first organization administrator. Its rules:

* **One-time, short-lived token.** On the first api start of an environment without an administrator,
  the api records `sha256(SETUP_TOKEN)` with `issued_at` in `setup_tokens` (the token itself is never
  stored or logged). It is valid for `SETUP_TOKEN_TTL_MINUTES` (default **60**) and is marked
  `consumed_at` by the first successful use. Comparison is constant-time on the hash.
* **Closed = 404.** Once an administrator exists (or in shared mode) `GET /api/v1/setup/status` and
  `POST /api/v1/setup/first-admin` return the same `404 {"detail":"Not Found"}` as an unknown route, and
  the `/setup` page redirects like an unknown route. Before that, an expired/used token gives
  `410 SETUP_TOKEN_EXPIRED` and the page tells the user to contact the operator.
* **Single-use; no re-activation by API or environment.** After the bootstrap row exists, `SETUP_TOKEN`
  is ignored; changing it (Key Vault, env, restart) does not re-open setup. Setup never opens again once
  an administrator exists. Operator CLIs inside the api container (no web route exists for any of them):
  ```bash
  az containerapp exec -n <client>-api -g rg-aqrem-<client> --command "python -m app.setup status"
  # token expired/lost BEFORE the first admin was created (refused once an admin exists):
  az containerapp exec -n <client>-api -g rg-aqrem-<client> --command "python -m app.setup reset --confirm"
  # forget failed attempts (lockout), all or one address:
  az containerapp exec -n <client>-api -g rg-aqrem-<client> --command "python -m app.setup clear-lockout --ip 203.0.113.5"
  # lost admin access AFTER setup (grants ORG_ADMIN; temp password printed once, must be changed):
  az containerapp exec -n <client>-api -g rg-aqrem-<client> --command \
    "python -m app.ops recover-admin --org <slug> --email admin@client.example --reset-password"
  ```
  `reset --confirm` revokes any unused token and generates a new one (printed **once** on your terminal;
  `--token-stdin` reads your own instead, min. 24 chars, never a previously used one). All three
  commands are audit-logged in the organization (`setup_reopened_by_operator`,
  `setup_lockout_cleared_by_operator`, `admin_recovered_by_operator`). `recover-admin` without
  `--reset-password` only grants the role to an existing user; for a new user it always creates a
  temporary password. Nothing is emailed.
* **Network gate.** The client address must be inside `SETUP_ALLOWED_CIDRS` (default: loopback and
  private ranges `127.0.0.0/8, ::1/128, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, fc00::/7`), otherwise 404.
  The `web` app is public, so on a fresh Azure environment `/setup` is **not** reachable from the
  internet until you set Terraform `setup_allowed_cidrs = ["<client admin IP>/32"]` (re-apply), or the
  admin connects through a private network/VPN. Remove the CIDR after setup.
  Which address counts: see "Which client IP the app sees" below.
* **Rate limit.** Failed token attempts are stored in `setup_attempts`. `SETUP_MAX_ATTEMPTS_PER_IP`
  (default 5) failures from one address, or `SETUP_MAX_ATTEMPTS_GLOBAL` (default 20) from all addresses,
  within `SETUP_LOCKOUT_MINUTES` (default 15) lock setup with `429` + `Retry-After` until the oldest
  failure leaves the window. While locked, even the correct token is refused. Requests outside the
  allowed networks are rejected before they count.
* **Logs.** `setup_token` keys and `setup_token=` values are redacted by the log filter, and the live
  token value is registered for literal redaction in every log line (app, uvicorn, uvicorn.access, celery).

### Which client IP the app sees
Azure documents for Container Apps HTTP ingress: *"X-Forwarded-For — The IP addresses of the client and/or
intermediate proxies that sent the request. If specified in initial request, it is appended to. Only the
rightmost IP is provided by Azure Container Apps. Any other values must be validated by the user to prevent
IP spoofing."* ([Ingress in Azure Container Apps → HTTP headers](https://learn.microsoft.com/en-us/azure/container-apps/ingress-overview#http-headers),
read 2026-10-17). The same page notes that `X-Forwarded-Proto` is overwritten, but `X-Forwarded-For` is only
appended to.

Request path in a dedicated environment: client → Container Apps ingress (envoy, appends the address it
saw) → `web` nginx (`proxy_add_x_forwarded_for` appends its peer, the envoy) → internal ingress → `api`.
The api therefore uses **`TRUSTED_PROXY_CIDRS`** (Terraform sets it to the environment's infrastructure
subnet, where ingress and replicas live):

* if the TCP peer is **not** in `TRUSTED_PROXY_CIDRS`, `X-Forwarded-For` is ignored and the peer is the client;
* if it is, the header is read **from the right**, skipping addresses that are themselves in
  `TRUSTED_PROXY_CIDRS`; the first other address is the client. Anything a client puts in the header sits
  to the left of Azure's entry and is never reached. A non-IP entry fails closed (404).

Empty `TRUSTED_PROXY_CIDRS` (default outside Terraform) = never trust the header. If you put another
proxy in front (Front Door, Application Gateway, a corporate proxy), add its egress range, or the gate
sees that proxy's address. Not verified against a live Azure environment yet; use the procedure below.

Every setup request logs one line with addresses only (no headers, no body, no token), logger `aqrem.setup`:
`setup gate: client_ip=203.0.113.5 via=forwarded peer=10.50.0.4 forwarded_entries=2 allowed=False`.
`via` is `peer`, `forwarded` or `invalid`.

### Real-deployment test procedure (run once per new environment, before handing out the token)
Prerequisites: environment deployed, no admin yet, `setup_allowed_cidrs = ["<A>/32"]` where A is the
public IP of the test machine "allowed" (`curl -s https://api.ipify.org`), and a second machine "other"
with a different public IP (phone hotspot, cloud shell). `FQDN` = web app FQDN.

1. From **allowed**:
   ```bash
   curl -s -o /dev/null -w '%{http_code}\n' https://$FQDN/api/v1/setup/status      # expect 200
   curl -s https://$FQDN/api/v1/setup/status | python3 -m json.tool                  # expect JSON:
   # {"deployment_mode": "dedicated", "setup_required": true, "organization_name": "...",
   #  "setup_token_configured": true, "license_state": ..., "expires_at": "<ISO time>"}
   ```
2. From **allowed**, spoof attempt (must still be judged by the real address, i.e. remain 200 for A, and
   on **other** remain 404):
   `curl -s -o /dev/null -w '%{http_code}\n' -H 'X-Forwarded-For: 10.0.0.1' https://$FQDN/api/v1/setup/status`
3. From **other**:
   ```bash
   curl -s -o /dev/null -w '%{http_code}\n' https://$FQDN/api/v1/setup/status        # expect 404
   curl -s https://$FQDN/api/v1/setup/status                                          # expect {"detail":"Not Found"}
   curl -s -o /dev/null -w '%{http_code}\n' -H 'X-Forwarded-For: 10.0.0.1' https://$FQDN/api/v1/setup/status  # expect 404
   curl -s -o /dev/null -w '%{http_code}\n' https://$FQDN/api/v1/no-such-route       # expect 404 (same body)
   ```
4. Read what the app saw (addresses only):
   ```bash
   az containerapp logs show -n <client>-api -g rg-aqrem-<client> --tail 200 | grep 'setup gate:'
   ```
   Expect `client_ip=<A> via=forwarded allowed=True` for step 1/2 and `client_ip=<other IP> ... allowed=False`
   for step 3. If `client_ip` shows a `10.x`/`100.x` address with `via=peer`, the peer is not in
   `TRUSTED_PROXY_CIDRS` (check the infrastructure subnet); if it shows a private address with
   `via=forwarded`, an extra proxy hop is in the trusted range — **stop and fix before continuing**.
5. Do not submit the form during the test (no token is needed for these checks).

### Delivering the setup token to the client admin
* **Separate channels.** Send the URL by email/ticket; send the token through a different channel: read it
  out by phone/video call after verifying the person, or a one-time secret link that expires after the
  first view (e.g. your password manager's one-time share). Never put URL and token in the same message,
  and never send the token in plain-text email or chat.
* **Short window.** The token is valid `SETUP_TOKEN_TTL_MINUTES` (60) after the first api start. Schedule the
  hand-over: deploy, run the test procedure above, then have the admin on the call and complete setup
  together. If it expires: `python -m app.setup reset --confirm`, deliver the new token the same way.
* **Narrow network.** Set `setup_allowed_cidrs` to the admin's IP only for the session, then remove it
  (re-apply) after setup.
* **Afterwards.** Setup closes for good when the admin is created. The Key Vault secret `setup-token` is
  useless then; you may disable it (`az keyvault secret set-attributes --enabled false ...`).
  Confirm `GET /api/v1/setup/status` returns 404.

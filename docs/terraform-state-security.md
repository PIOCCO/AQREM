# Terraform state security

> Status: the state stack, backends and scripts pass `terraform fmt` / `init -backend=false` / `validate`
> locally. **Nothing here has been applied or planned against Azure yet.**

## Layout

| Stack | Container | Key |
|---|---|---|
| `stacks/state` (the state account itself) | `tfstate-platform` (after `-migrate-state`) | `state/bootstrap.tfstate` |
| `stacks/platform` | `tfstate-platform` | `platform/<env>.tfstate` |
| root `infra/terraform` (Azure OpenAI) | `tfstate-platform` | `openai/<env>.tfstate` |
| `stacks/dedicated` per client (`scripts/new-client-env.sh`) | **`tfstate-<client>`** | `dedicated/<client>.tfstate` |

One storage account (`stacks/state`), **one container per dedicated client**: the container is the
RBAC boundary, so a principal granted on `tfstate-contoso` cannot read `tfstate-fabrikam`.
`new-client-env.sh` refuses to run without `AQREM_TFSTATE_RG`/`AQREM_TFSTATE_ACCOUNT` unless
`--allow-local-state` is passed (sandbox only).

## Controls on the state account (`infra/terraform/stacks/state/main.tf`)
* **Entra ID only**: `shared_access_key_enabled = false` (no account keys, no SAS),
  `default_to_oauth_authentication = true`; every backend uses `use_azuread_auth = true`
  (HashiCorp recommends Entra ID; access keys/SAS are "not recommended for new workloads" —
  [azurerm backend docs](https://developer.hashicorp.com/terraform/language/backend/azurerm)).
* **Least-privilege data access**: `Storage Blob Data Contributor` on the **container** (the role the
  backend docs recommend "for least privilege"), only for principals listed in
  `platform_state_principal_ids`, `client_state_principal_ids[<client>]`, `all_clients_principal_ids`.
* **Encryption at rest**: Azure Storage service encryption (always on) + `infrastructure_encryption_enabled`
  (second layer). Customer-managed keys are not configured (decision for you, see below).
* **Transport**: `min_tls_version = TLS1_2`, HTTPS only, no public blob/container access.
* **Recovery**: blob versioning + soft delete for blobs and containers (`soft_delete_days`, default 30),
  `CanNotDelete` management lock, `prevent_destroy`.
* **Locking**: the azurerm backend locks with a **blob lease** on the state blob ("supports state locking
  and consistency checking with Azure Blob Storage native capabilities"); no extra table. A crashed run
  leaves a lease: `terraform force-unlock <LOCK_ID>` after confirming nobody else is running.
* **Network (optional)**: `allowed_ip_cidrs` → firewall default `Deny`; `public_network_access_enabled = false`
  for private-endpoint-only (then run Terraform from inside the VNet).

Create it once: `scripts/tfstate-bootstrap.sh` (plan → confirm → apply; `--validate-only` makes no
Azure calls), then migrate the bootstrap stack's own state into `tfstate-platform` as the script prints.
Add each new client id to `clients` and re-apply **before** `new-client-env.sh` for that client.

## Who can read state
Anyone who can read the blob, i.e. principals with, at container scope **or inherited from
account / resource group / subscription**:
* `Storage Blob Data Reader`, `Storage Blob Data Contributor`, `Storage Blob Data Owner`;
* roles that can *grant* those or re-enable keys: `Owner`, `User Access Administrator`,
  `Role Based Access Control Administrator`, and `Storage Account Contributor`/`Contributor`
  (management plane: can set `shared_access_key_enabled = true` and list keys). Keep these few; consider an
  Azure Policy that denies storage accounts with shared key access enabled.

Audit: `az role assignment list --scope <account-id>/blobServices/default/containers/tfstate-<client> --include-inherited -o table`
and enable the storage account's diagnostic logs (`StorageRead`) to a Log Analytics workspace if you need
read auditing (not configured by default).

## Grant / revoke
Preferred: edit the principal maps in `stacks/state/terraform.tfvars` and re-apply (reviewable, reverts drift).
Break-glass with the CLI (same effect):
```bash
SCOPE="$(az storage account show -n <account> -g rg-aqrem-tfstate --query id -o tsv)/blobServices/default/containers/tfstate-<client>"
az role assignment create --assignee-object-id <object-id> --assignee-principal-type User \
  --role "Storage Blob Data Contributor" --scope "$SCOPE"
az role assignment delete --assignee <object-id> --role "Storage Blob Data Contributor" --scope "$SCOPE"
```
Revocation takes effect for new tokens; Entra access tokens already issued stay valid until expiry
(up to ~1 h). For an urgent revoke also disable the user / revoke sessions in Entra.
Read-only reviewers: grant `Storage Blob Data Reader` instead.

## What can still land in state (azurerm 4.81, checked with `terraform providers schema -json`)
Secrets **kept out** of state/plan (ephemeral values + write-only attributes, Terraform >= 1.11):
`secret_key`, `setup_token`, PostgreSQL admin/app passwords and the database URLs (dedicated),
`AQREM_EXISTING_*DATABASE_URL` (ephemeral variables), tenant DB password (`client_stack`),
control-plane PostgreSQL admin password (`administrator_password_wo` + `value_wo`, now ephemeral),
gateway internal provisioning token (now ephemeral → Key Vault `value_wo` → Container App Key Vault reference).
Write-only attributes available in this provider for our resources: only
`azurerm_postgresql_flexible_server.administrator_password_wo` and `azurerm_key_vault_secret.value_wo`.
Container App `secret.value` has **no** write-only variant; use `key_vault_secret_id` + identity.

Still in state (provider-exported attributes, no write-only option):

| Where | Attribute | Notes |
|---|---|---|
| `azurerm_storage_account` (dedicated, client_stack, state) | `primary/secondary_access_key`, connection strings | Shared key is disabled on dedicated + state accounts, so a leaked key is not usable unless someone re-enables shared key; whether the provider still records them with shared key off is **unverified** — check after the first apply. `client_stack` (shared-tier) account still has shared key **enabled** (provider default): its keys are in state and usable — decision pending. |
| `azurerm_cognitive_account` (root + platform `openai`) | `primary/secondary_access_key` | Apps use managed identity; with `local_auth_enabled = false` keys are not accepted by the service. |
| `modules/openai` `azurerm_key_vault_secret.openai_api_key` | `value` = account key | Only when `store_api_key_in_key_vault = true` (opt-in fallback). |
| `azurerm_log_analytics_workspace` (platform monitoring) | `primary/secondary_shared_key` | Agent ingestion keys. |
| `azurerm_application_insights` | `instrumentation_key`, `connection_string` | Ingestion-only; also passed into the gateway Container App as `secret.value` (`appinsights-cs`). |
| `modules/model_gateway_custom` legacy path | `secret.value` = provisioning token | Only if a caller sets `internal_provisioning_token` without the Key Vault id (platform stack no longer does). |
| `azurerm_api_management` (if enabled) | `tenant_access` keys | Only if tenant access is enabled. |

Plan files (`-out=tfplan`) contain the same plus values of non-ephemeral sensitive variables; Terraform masks
sensitive values **on screen only**. Scripts keep plans 0600 in gitignored dirs and delete them after apply/abort.
Never attach plan files or `terraform show -json` output to tickets/CI artifacts.

Audit a real state without writing it to disk:
`terraform state pull | python3 scripts/check_secrets.py --stdin` (prints masked findings only).

## Rotating secrets that appeared in state
Assume compromise if a state/plan file left its container (laptop copy, artifact, wrong RBAC grant).
Old blob **versions** keep old values; after rotating, they only hold dead credentials (delete them if policy requires:
`az storage blob delete --version-id ...`).

1. **Contain**: revoke the extra access (above); note the time window from storage logs if enabled.
2. **Dedicated environment generated secrets** (`secret_key`, setup token, PostgreSQL passwords, DB URLs):
   bump `secrets_version` for that client and apply — the write-only values are regenerated and re-written to
   the server and Key Vault in one run. Then restart api/worker/beat (`az containerapp revision restart`) so
   they load the new Key Vault values. Note: a new `secret_key` signs out every user.
3. **Existing (bring-your-own) PostgreSQL**: change the role passwords in the database
   (`ALTER ROLE aqrem_app PASSWORD ...` as owner), export the new `AQREM_EXISTING_*DATABASE_URL`, re-run
   `new-client-env.sh <client> ... --existing-db` with a bumped `secrets_version`, restart the apps.
4. **Storage account keys**: `az storage account keys renew -g <rg> -n <account> --key primary` then `--key secondary`
   (harmless while shared key is disabled; do it anyway after a leak).
5. **Azure OpenAI keys**: `az cognitiveservices account keys regenerate -g <rg> -n <account> --key-name Key1`
   then `Key2`; if `store_api_key_in_key_vault` is on, apply again so Key Vault gets the new key.
6. **Log Analytics shared keys**: regenerate via the portal (Agents → Regenerate) or the
   `workspaces/regenerateSharedKey` REST action; agents using managed identity are unaffected.
7. **Application Insights**: the connection string cannot be rotated; it only allows sending telemetry.
   If abuse matters, create a new component and switch the connection string.
8. **Gateway provisioning token**: bump `secrets_version` in the platform stack and apply; restart the gateway.
9. **Setup token**: irrelevant after setup (single use); before setup run `python -m app.setup reset --confirm`.
10. Verify: `terraform state pull | python3 scripts/check_secrets.py --stdin` and smoke-test the apps.

## Repository hygiene
* `.gitignore` (root + `infra/terraform/.gitignore`): state, plans, crash logs, `.terraform/`, real tfvars,
  `backend.hcl`, `.env*`, keys/certs; only `*.example`, `envs/*.tfvars` (no secrets) and `*.sample.tfvars.json`
  are tracked. `clients/` is anchored to `infra/terraform/clients/` (it previously also hid
  `parameters/clients/`).
* `python3 scripts/check_secrets.py` (tracked files), `--history` (all commits), `--staged` (pre-commit),
  `--stdin`. Output is masked. Install the hook with `scripts/install-git-hooks.sh`.
* CI: the workflow files are not changed by this repo's automation (token lacks the `workflow` scope).
  Add a step to an existing job yourself:
  ```yaml
      - name: Secret / state-file scan
        run: |
          python3 scripts/check_secrets.py
          python3 scripts/check_secrets.py --history
  ```
  (`actions/checkout` needs `fetch-depth: 0` for `--history`.) `scripts/run-security-checks.sh` runs both locally.

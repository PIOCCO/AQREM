# Azure OpenAI with Terraform: audit, hardening and runbook

Status: 2026-10-16, branch `azure-terraform-hardening` (based on `azure-openai-final`).
Scope: the root OpenAI stack in `infra/terraform/` plus the shared module `infra/terraform/modules/openai/`
(also used by `infra/terraform/stacks/platform`). This doc doesn't cover the platform or client stacks.

> No `terraform plan` or `apply` was run against Azure. This machine has no Azure credentials.
> Every "Azure check" below is a command for you to run.

## 1. What existed and what was audited

A repo-wide search (`git ls-tree` over every `origin/*` branch) found Terraform already in place:

* `infra/terraform/` is the root "OpenAI-only" stack in an **existing** resource group. It uses
  `modules/openai`, and CI runs it in `.github/workflows/terraform-iac.yml` (fmt, init -backend=false, validate on TF 1.11.4).
* `infra/terraform/stacks/platform` and `stacks/client` are the larger platform stacks. They have their own lock files and `backend.tf.example`.
* The unmerged branch `origin/cursor/azure-openai-terraform-00e3` holds an older copy of the same module. It wasn't used.

So the repo's existing configuration was audited and fixed with minimal changes. No new `infra/azure-openai/` tree was created.
The chat-only sketch (new RG `${prefix}-ai-rg`, `random_string` subdomain, `primary_access_key` output,
embed `depends_on` chat) was audited too. Its defects are listed with the repo's own.

### Defects found

| # | Where | Defect | Fix |
|---|---|---|---|
| 1 | repo + sketch | **`text-embedding-3-small` v1 has no regional `Standard` offer in swedencentral** (Microsoft region table, Standard/Regional section, shows "-"). The repo used one `deployment_sku_name = "Standard"` for both deployments, and the sketch used `Standard` for embeddings. Apply would fail. | Each deployment now has its own type (`chat_/embedding_deployment_sku_name`). Default is `GlobalStandard`; prod tfvars use `DataZoneStandard`. Validation restricts the value to real deployment types. |
| 2 | repo + sketch | **`gpt-4o-mini` 2024-07-18 is "Deprecated"** in the retirement schedule (retires **2027-04-14**). Deprecated means *existing customers only*: a subscription that never deployed this version can't create new deployments. | The version wasn't changed silently. It's kept and flagged in tfvars and here. Section 3 covers the migration choice. |
| 3 | repo | No `version_upgrade_option`. The provider default `OnceNewDefaultVersionAvailable` lets Azure switch model versions without notice. | Variable, default `OnceCurrentVersionExpired`: stay pinned until retirement, then auto-upgrade instead of returning `410 Gone`. |
| 4 | repo | Capacity described as "PTU/token capacity", default `1` (1K TPM, which throttles almost immediately). | Descriptions fixed (section 4). Explicit per-env values. |
| 5 | repo | Default name `aoai-aqrem-<env>` must be **globally unique** (it is the `*.openai.azure.com` subdomain) and could collide. No name validation. | Optional deterministic `name_suffix` (`aoai-aqrem-dev-sc01`), regex validation (2–64 chars, alphanumerics and hyphens, alphanumeric at both ends), plus a precondition in the module. |
| 6 | sketch | `random_string` suffix with the `random` provider not declared in `required_providers`, no `keepers`. | Replaced by the deterministic `name_suffix`. No `random` provider is needed in the root stack. |
| 7 | sketch | `output primary_access_key` (`sensitive = true`). `sensitive` only hides the value in CLI output. The key is still written in plaintext to state, and anyone with state read access gets it. | No key output exists. The module's optional `azurerm_key_vault_secret` (default off) has the same state exposure. It's now documented and blocked when `local_auth_enabled = false`. |
| 8 | repo | `local_auth_enabled` not set (API keys always accepted). | Variable. `false` in prod, which forces Entra ID. `true` in dev, because the Pi needs a key. |
| 9 | repo | Public endpoint open to the whole internet with no ACL option. | `network_acls_default_action` + `allowed_ip_rules` (validated IPv4/CIDR). `public_network_access_enabled` stays a variable. |
| 10 | repo | No remote backend. State would be local, unlocked and unencrypted on a laptop. | `backend "azurerm" {}` (partial config) + `backend.hcl.example` with `use_azuread_auth = true`. |
| 11 | repo | `.gitignore` missed `*.tfplan`, `backend.hcl`, `crash.*.log`, `.terraform.tfstate.lock.info`. | Updated. `envs/*.tfvars` (secret-free) and the sample client tfvars are re-included. `.terraform.lock.hcl` stays committed. |
| 12 | repo | No protection against accidental destroy in prod. | Optional `CanNotDelete` management lock (`enable_delete_lock = true` in prod). `prevent_destroy` can't be variable-driven, so a lock is used. |
| 13 | repo | No managed identity on the account and no outbound restriction. | System-assigned identity (needed later for CMK). `outbound_network_access_restricted = true` (AQREM only calls chat/embeddings). |
| 14 | repo | Module had no `terraform {}` block (tflint `required_version`/`required_providers`). | `modules/openai/versions.tf` (`azurerm >= 4.0, < 5.0`). |
| 15 | sketch | `embedding depends_on chat`. | Not needed. The provider locks the parent account for deployment create/update/delete since v3.70 ([#22607](https://github.com/hashicorp/terraform-provider-azurerm/issues/22607), [#22711](https://github.com/hashicorp/terraform-provider-azurerm/commit/3d399deafbabe3af81e3375278d70066cabd76c6), [#22939](https://github.com/hashicorp/terraform-provider-azurerm/issues/22939)). It prevents the Azure `409 RequestConflict: Another operation is being performed on the parent resource`. The repo module never had the `depends_on`, and none was added. |
| 16 | sketch | Creates its own RG `${prefix}-ai-rg`. | Repo convention (root stack reuses an existing RG; the platform stack creates RGs) kept. |
| 17 | info | azurerm **5.x** (5.10.0) is now the current major. The repo is on 4.x (lock 4.81.0, the latest 4.x). | Root pin tightened to `~> 4.81`. Moving to 5.x touches all three stacks and should be its own change. |

Kept as is: RG data source, `kind = "OpenAI"`, `sku_name = "S0"` (now validated, the only SKU for OpenAI accounts),
`rai_policy_name = "Microsoft.Default"`, the RBAC role assignment (`Cognitive Services OpenAI User`, inference only, no key listing),
and the non-secret `aqrem_backend_env` output.

## 2. Changed files

| File | Why |
|---|---|
| `infra/terraform/versions.tf` | `required_version >= 1.11.0` (CI pin 1.11.4; validated with 1.11.4 and 1.16.6). `azurerm ~> 4.81`. Partial `backend "azurerm" {}`. |
| `infra/terraform/variables.tf` | New typed/validated variables (below). Fixed capacity/SKU descriptions. Validation on name, suffix, SKU, IP rules, upgrade option, KV/local-auth combination. |
| `infra/terraform/locals.tf` | Deterministic name `aoai-<project>-<env>[-<suffix>]`. Allowed deployment types. |
| `infra/terraform/openai.tf` | Passes the new variables to the module. |
| `infra/terraform/outputs.tf` | Added SKU, `local_auth_enabled`, account identity, embedding-dimension and RBAC guidance outputs. No secrets. |
| `infra/terraform/modules/openai/main.tf` | Per-deployment SKU, `version_upgrade_option`, `local_auth_enabled`, identity, `network_acls`, outbound restriction, name precondition, optional lock, optional Audit-only diagnostics. |
| `infra/terraform/modules/openai/{variables,outputs,versions}.tf` | New inputs/outputs (all defaulted, so `stacks/platform` keeps validating), provider constraint. |
| `infra/terraform/envs/dev.tfvars`, `envs/prod.tfvars` | Per-environment values, no secrets. |
| `infra/terraform/backend.hcl.example` | Remote state template (Entra ID auth, no storage keys). |
| `infra/terraform/.gitignore` | State, plans, backend.hcl, crash logs. |
| `infra/terraform/tests/openai_envs.tftest.hcl`, `tests/envfile/env_file.tftest.hcl` | Offline `terraform test` with a mocked azurerm provider: naming, auth flags, validation failures, and a plan of each env file. |
| `docs/azure-terraform.md` (this file), `docs/azure-openai-setup.md` | Runbook and Entra ID / Terraform notes. |

### Variables

| Variable | dev | prod | Notes |
|---|---|---|---|
| `environment` | `dev` | `production` | Existing validation: dev, staging, production |
| `location` | `swedencentral` | `swedencentral` | |
| `resource_group_name` | `rg-aqrem-dev` | `rg-aqrem-prod` | Must exist already |
| `name_suffix` | `sc01` | `sc01` | Set once. Changing it replaces the account |
| `deployment_sku_name` | `GlobalStandard` | `DataZoneStandard` | Overridable per deployment |
| `chat_model_name/version` | `gpt-4o-mini` / `2024-07-18` | same | Deprecated, see section 3 |
| `chat_capacity` | 10 | 30 | ×1K TPM |
| `embedding_model_name/version` | `text-embedding-3-small` / `1` | same | |
| `embedding_capacity` | 30 | 100 | ×1K TPM |
| `embedding_dimensions` | 1536 | 1536 | Must match `EMBEDDING_DIMENSIONS` + pgvector |
| `version_upgrade_option` | `OnceCurrentVersionExpired` | same | |
| `local_auth_enabled` | `true` | `false` | |
| `public_network_access_enabled` | `true` | `true` (+ ACL Deny) | Set false once a private endpoint exists |
| `network_acls_default_action` / `allowed_ip_rules` | Allow / [] | **Deny / [] (fill in egress IPs before apply)** | |
| `outbound_network_access_restricted` | true (default) | true | |
| `enable_delete_lock` | false | true | |
| `managed_identity_principal_id` | optional | app MI object ID | Grants Cognitive Services OpenAI User |
| `log_analytics_workspace_id` | optional | optional | Audit logs + metrics only |
| `store_api_key_in_key_vault` | false | false (rejected when local auth is off) | Puts key in state |

## 3. Model availability (checked 2026-10-16)

Sources:
* Region availability (page updated 2026-09-04):
  https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure-region-availability?pivots=standard
* Retirement schedule (updated 2026-09-23): https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/model-retirement-schedule
* Lifecycle policy: https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/model-retirements
* Model catalog: https://learn.microsoft.com/en-us/azure/ai-foundry/openai/concepts/models

| Model / version | GlobalStandard swedencentral | DataZoneStandard swedencentral | Standard (regional) swedencentral | Lifecycle | Retirement |
|---|---|---|---|---|---|
| gpt-4o-mini 2024-07-18 | ✅ | ✅ | ✅ | **Deprecated** (existing customers only) | **2027-04-14** |
| text-embedding-3-small 1 | ✅ | ✅ | **❌ not offered** | GA | 2028-02-09 |

What follows from the table:
* **Deprecated means a new subscription may be refused.** The policy says new customers can't create deployments.
  "Existing customer" is decided per subscription (has it ever deployed that model version?). Check before applying (section 6, `az cognitiveservices model list`).
  If `gpt-4o-mini` isn't deployable, or for anything planned beyond April 2027, set a GA successor explicitly in tfvars.
  For example `gpt-5.4-mini` 2026-03-17 (GA, retires 2027-09-21, GlobalStandard + DataZoneStandard in swedencentral), or
  `gpt-5-mini` 2025-08-07 (GA, retires 2027-02-09). These are **reasoning models**: test AQREM's prompts, `temperature` and
  `max_tokens` handling first. `gpt-4.1-mini` 2025-04-14 is also Deprecated (2027-04-14), so it doesn't buy any time.
* With `OnceCurrentVersionExpired`, Azure upgrades a retiring Standard/Global/DataZone deployment automatically. After that, Terraform shows drift on
  `model.version`. Update the tfvars to the new version instead of reverting.
* Embedding model changes require re-indexing (`docs/azure-openai-setup.md` §3). `text-embedding-3-small` returns 1536 dimensions.

### Deployment type and data processing location

From the region-availability page and the privacy page:
* **GlobalStandard**: prompts and responses "might be processed in any Azure region where the model is deployed". Cheapest option.
* **DataZoneStandard (EU)**: processed within the EU data zone. About 10% dearer.
* **Standard (regional)**: processed in the deployment's region. Same price as DataZone for gpt-4o-mini. Not available for the embedding model here.
* For all types, data at rest (including the abuse-monitoring store) stays in the resource's geography.

## 4. Capacity units

For Standard, GlobalStandard and DataZoneStandard deployments, `capacity` is a **rate limit**: 1 unit = 1,000 tokens per minute.
It consumes your per-subscription, per-region, per-model, per-deployment-type **quota**. It is **not** a budget or a spending cap,
and an idle deployment costs nothing. Billing is per token (pay-as-you-go). Requests per minute scale with TPM (for gpt-4o-mini, about 6 RPM per 1K TPM).
**PTU** (provisioned throughput, `*ProvisionedManaged`) is different: capacity is a number of reserved PTUs billed hourly
whether used or not. It isn't used here. Check quota with `az cognitiveservices usage list --location swedencentral`.

Sizing: prod chat at 30 units (30K TPM) handles about 6 questions per minute at ~4.5K tokens each. That's plenty for 3,000 per week.
Embedding at 100K TPM is for bulk re-indexing. Raising capacity is an in-place update.

## 5. Naming, idempotency, replacement

* Account name = custom subdomain = endpoint host. It's deterministic: `aoai-aqrem-<env>[-<suffix>]`.
  Without a random provider there's no state-held randomness, and a second workspace always reproduces the same name.
* **Changing `openai_account_name`, `name_suffix`, `environment`, `project_name` or `location` replaces the account.** That means a new endpoint,
  both deployments recreated, new keys and role assignments. The old name stays reserved in soft-delete (48 h) unless purged.
  `purge_cognitive_account_on_destroy` is `true` only in dev.
* Changing a deployment's `name`, model `name`, or SKU name replaces that deployment. The app sees `DeploymentNotFound` until it's back.
  Model `version` and `capacity` are in-place updates.
* The prod `CanNotDelete` lock blocks the account and its deployments from deletion. Remove it deliberately
  (`terraform apply -var enable_delete_lock=false` or portal) before any planned replacement.

## 6. Commands

### Checks that need Azure (not done here, run them yourself)

```bash
az login
az account set --subscription "<subscription-id>"
export ARM_SUBSCRIPTION_ID="$(az account show --query id -o tsv)"

# Is the model/version/SKU deployable for THIS subscription in the region? (deprecated => may be missing)
az cognitiveservices model list --location swedencentral \
  --query "[?model.name=='gpt-4o-mini' || model.name=='text-embedding-3-small'].{name:model.name, version:model.version, lifecycle:model.lifecycleStatus, skus:model.skus[].name}" -o table

# Remaining quota (TPM) per model and deployment type
az cognitiveservices usage list --location swedencentral -o table

# Global name availability for the subdomain
az cognitiveservices account list --query "[?name=='aoai-aqrem-dev-sc01']" -o table
az cognitiveservices account list-deleted -o table   # soft-deleted names are still reserved
```

### Remote state (one-time, manual; not migrated by this change)

```bash
RG=rg-aqrem-tfstate; SA=staqremtfstate01; LOC=swedencentral
az group create -n $RG -l $LOC
az storage account create -n $SA -g $RG -l $LOC --sku Standard_ZRS --kind StorageV2 \
  --min-tls-version TLS1_2 --https-only true --allow-blob-public-access false \
  --allow-shared-key-access false --default-action Deny --bypass AzureServices
# encryption at rest (AES-256, Microsoft-managed keys) is always on; add CMK if required
az storage account blob-service-properties update -n $SA -g $RG \
  --enable-versioning true --enable-delete-retention true --delete-retention-days 30 \
  --enable-container-delete-retention true --container-delete-retention-days 30
az storage account network-rule add -n $SA -g $RG --ip-address "<your-egress-ip>"
az storage container create -n tfstate --account-name $SA --auth-mode login
az role assignment create --assignee "<your-or-CI-object-id>" --role "Storage Blob Data Contributor" \
  --scope "$(az storage account show -n $SA -g $RG --query id -o tsv)/blobServices/default/containers/tfstate"
az lock create -n tfstate-nodelete -g $RG --lock-type CanNotDelete
```

The azurerm backend takes a **blob lease** during operations, which gives state locking. Restrict the container to the operators/CI only:
state contains resource IDs, and would contain the key if `store_api_key_in_key_vault` were enabled.
If you already have a local `terraform.tfstate` from the old root stack, migrate it deliberately with
`terraform init -backend-config=backend.hcl -migrate-state`. That wasn't done here.

### Init / validate / plan / apply

```bash
cd infra/terraform
cp backend.hcl.example backend.hcl            # edit names; key openai/dev.tfstate or openai/production.tfstate
terraform fmt -check -recursive
terraform init -backend-config=backend.hcl
terraform validate
terraform test                                 # offline, mocked provider
terraform test -test-directory=tests/envfile -var-file=envs/dev.tfvars
terraform plan  -var-file=envs/dev.tfvars -out dev.tfplan
terraform apply dev.tfplan
# prod: separate state key (backend.hcl with key=openai/production.tfstate, or `terraform init -reconfigure`)
#   fill allowed_ip_rules / managed_identity_principal_id in envs/prod.tfvars first
terraform plan  -var-file=envs/prod.tfvars -out prod.tfplan
terraform apply prod.tfplan
terraform output aqrem_backend_env
```

Getting a key for dev or the Raspberry Pi (never through Terraform output):

```bash
# into Key Vault directly (value never printed):
az keyvault secret set --vault-name <kv> --name aqrem-azure-openai-api-key \
  --value "$(az cognitiveservices account keys list -n aoai-aqrem-dev-sc01 -g rg-aqrem-dev --query key1 -o tsv)" >/dev/null
# or on the Pi, into the gitignored .env (chmod 600), using the same command substitution.
# Rotate with: az cognitiveservices account keys regenerate --key-name key2 ...
```

## 7. Validation results (this machine, 2026-10-16)

| Check | Result |
|---|---|
| Terraform 1.16.6 (official HashiCorp linux_amd64 zip, SHA256 verified) and 1.11.4 (CI pin) | installed |
| `terraform fmt -check -recursive` (infra/terraform) | **pass** (1.16.6 and 1.11.4) |
| `terraform init -backend=false` | **pass** (azurerm 4.81.0 from the existing lock, lock file unchanged) |
| `terraform validate` root | **pass** (both versions) |
| `terraform validate` stacks/platform, stacks/client (shared module) | **pass** |
| `terraform test` (4 runs, mocked provider) | **pass** |
| `terraform test -test-directory=tests/envfile` with dev and prod tfvars | **pass** |
| `terraform providers` | In the repo dir it errors with "Backend initialization required", because the backend block was only initialised with `-backend=false`. It passed in a copy without the backend block: `azurerm ~> 4.81`, `module.openai → azurerm`. |
| tflint 0.64.0 (repo `.tflint.hcl`, azurerm ruleset 0.29.0) root | **pass, 0 issues** |
| tflint modules/openai | 1 warning, pre-existing: `purge_cognitive_account_on_destroy` unused in the module (it's used by the provider block in callers) |
| checkov 3.x with prod tfvars, OpenAI resources | remaining: CKV_AZURE_134 (public network access, intentional until a private endpoint exists), CKV_AZURE_247 (DLP: outbound is restricted but no `fqdns` allow-list; the check wants both), CKV2_AZURE_22 (no CMK, not adopted), CKV_AZURE_41 (KV secret expiry on the default-off key secret). Dev additionally fails CKV_AZURE_236 (local auth on, intentional). |
| `terraform plan` / `apply`, quota, model list | **not run: no Azure auth** |

## 8. Security assessment

* **Secrets**: no secret is in code, tfvars or outputs. API keys are rejected in prod (`local_auth_enabled = false`).
  The optional Terraform-managed Key Vault secret is off by default and puts the key in state. Prefer the manual `az` commands above.
* **State**: remote, Entra ID-authenticated (no storage keys, shared-key access disabled), encrypted at rest, versioned with soft delete,
  lease-locked, network-restricted. Note that `sensitive = true` never keeps a value out of state.
* **Identity**: app → account uses `Cognitive Services OpenAI User` (data-plane inference only; it can't list keys or manage deployments).
  The deployer needs `Cognitive Services Contributor` (or Contributor) on the RG, plus `User Access Administrator`/RBAC Administrator
  only if Terraform creates the role assignment. **Managed identity only works when AQREM runs in Azure** (Container Apps/App Service/VM).
  The Raspberry Pi can't use it. It uses an API key from `.env` (`chmod 600`) or a service-principal secret through `DefaultAzureCredential`
  env vars. Either way it's a secret on the device, so keep `local_auth_enabled = true` only on the account the Pi calls.
* **Network**: HTTPS only (TLS endpoint, no HTTP listener). Dev is public, optionally IP-restricted. Prod has ACL Deny with an allow-list until a
  private endpoint exists, then `public_network_access_enabled = false`. A private endpoint isn't created by this stack (opt-in later,
  needs VNet + `privatelink.openai.azure.com` DNS zone; cost in section 9). Outbound from the account is restricted.
* **Customer data**: AQREM sends the user's question **plus the retrieved document chunks** of that organisation to the model endpoint
  (and document text to the embedding endpoint). Per Microsoft's
  [Data, privacy, and security for Foundry Models sold by Azure](https://learn.microsoft.com/en-us/azure/foundry/responsible-ai/openai/data-privacy)
  (change log entry 3 Oct 2025): prompts and completions aren't available to other customers or to OpenAI, aren't used to train models, and the models
  are stateless. Content is filtered in real time. **Abuse monitoring** may store flagged prompts and completions in the resource's geography for human review
  (reviewers in the EEA for EEA deployments). Turning that storage off ("modified abuse monitoring") requires an application and Microsoft approval.
  Verify it with the `ContentLogging=false` capability in `az cognitiveservices account show`.
  The processing location depends on deployment type (section 3). Use DataZoneStandard or regional Standard where EU-only processing is contractually required.
* **Logging**: only Audit logs + metrics are wired up (opt-in). No request/response content logging is enabled, and the app shouldn't log prompts either.
* **Tenant isolation is an app concern**: org-scoped retrieval is already implemented in AQREM (only the caller's organisation's chunks are
  sent). The model account is shared across tenants, so the guarantee comes from retrieval, not from Azure. A master/super-admin who can read customer
  content is an application decision. Recommended controls: no default content access for platform admins, just-in-time and audited break-glass,
  an audit log of admin reads, and disclosure in customer terms.

## 9. Cost assessment (estimates, USD, list prices, excluding tax/discounts)

Source: Azure Retail Prices API (`https://prices.azure.com/api/retail/prices`, `serviceName eq 'Foundry Models'`,
`armRegionName eq 'swedencentral'`), queried 2026-10-16. Per 1M tokens:

| Meter | Global | Data Zone | Regional |
|---|---|---|---|
| gpt-4o-mini 0718 input | $0.15 | $0.165 | $0.165 |
| gpt-4o-mini 0718 cached input | $0.075 | $0.083 | $0.091 |
| gpt-4o-mini 0718 output | $0.60 | $0.66 | $0.66 |
| text-embedding-3-small | $0.020 | $0.022 | $0.025 (meter exists, deployment type not offered in swedencentral per docs) |

Other items:
* Account S0: no fixed charge. PTU: not used (hourly reserved, far more expensive at this volume).
* Private endpoint (only if enabled): about $0.01/hour, so about $7.30/month, plus about $0.01/GB processed. The Private Link pricing page renders prices
  dynamically and the API filter returned nothing, so **verify these figures**. Private DNS zone: $0.50/zone/month (Retail API).
* Log Analytics (Retail API, swedencentral): ingestion $2.99/GB after the first 5 GB/month, retention $0.13/GB/month beyond the free period.
  Audit-only logs are far below 1 GB per month, so about $0.
* State storage (Hot LRS $0.0184/GB/month, writes $0.05/10K): under $0.10/month. ZRS is slightly more and still pennies.

Scenarios (gpt-4o-mini + text-embedding-3-small; uncached input; estimate):

| Scenario | Tokens per month | Global | Data Zone |
|---|---|---|---|
| Dev light use: 500 questions × (4K in + 500 out), 1M embedding tokens | 2M in, 0.25M out, 1M emb | ≈ $0.47 | ≈ $0.52 |
| 30-user customer: 3,000 questions/week ≈ 13,000/month × (4K in + 500 out) | 52M in, 6.5M out | ≈ $11.70 | ≈ $12.87 |
| + query embeddings (≈30 tokens × 13K) + indexing 5M tokens per month | ≈ 5.4M emb | ≈ $0.11 | ≈ $0.12 |
| + optional private endpoint + DNS | | ≈ $7.80 | ≈ $7.80 |

Prompt caching (repeated system prompt prefix ≥1,024 tokens) can lower input cost. Treat these as order-of-magnitude figures.
Use the Azure pricing calculator with your agreement for real quotes.

## 10. Remaining limitations and manual actions

1. Run the Azure checks in section 6 (model deployability for a *deprecated* version, quota, name availability) before the first plan.
2. Decide the chat model: keep gpt-4o-mini (works only for "existing customer" subscriptions, retires 2027-04-14) or set a GA model in tfvars and test it.
3. Fill `allowed_ip_rules` and `managed_identity_principal_id` in `envs/prod.tfvars`. With Deny and an empty list, prod rejects every caller.
4. Create the state storage account (section 6). Migrate any existing local state yourself.
5. Private endpoint, CMK, the `fqdns` allow-list and the azurerm 5.x upgrade aren't implemented.
6. If you need EU-only processing, apply to Microsoft for modified abuse monitoring (needs approval) and update customer data-processing terms.
7. CI (`terraform-iac.yml`) still runs on TF 1.11.4 and doesn't run `terraform test`. Consider adding the `terraform test` steps.

# AQREM — Azure OpenAI (Terraform)

Production-oriented Terraform for the **Azure OpenAI** account and **model deployments** used by AQREM (chat answers + evidence embeddings). This stack **does not** deploy Container Apps, PostgreSQL, Redis, or the AQREM application — only OpenAI resources inside an **existing** resource group.

## Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/install) `>= 1.6`
- [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) logged in: `az login`
- Permissions to create **Cognitive Services / OpenAI** resources and deployments in the target subscription
- An **existing** resource group (this module does not create one)
- Model availability in your region ([Azure OpenAI model catalog](https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/models))

## Azure authentication

```bash
az login
az account set --subscription "<subscription-id>"
export ARM_SUBSCRIPTION_ID="<subscription-id>"
```

For CI/CD, use a service principal or OIDC and set `ARM_CLIENT_ID`, `ARM_CLIENT_SECRET`, `ARM_TENANT_ID`, `ARM_SUBSCRIPTION_ID`.

## Terraform initialization

```bash
cd infra/terraform
terraform init
```

## Variables

| Variable | Purpose |
|----------|---------|
| `subscription_id` | Optional; defaults to CLI context |
| `resource_group_name` | **Existing** RG (required) |
| `location` | Azure region |
| `environment` | `dev` \| `staging` \| `production` |
| `project_name` | Name slug (default `aqrem`) |
| `chat_*` | Chat model name, version, deployment name, capacity |
| `embedding_*` | Embedding model name, version, deployment name, capacity |
| `embedding_dimensions` | Must match model output and AQREM `EMBEDDING_DIMENSIONS` / pgvector |
| `managed_identity_principal_id` | AQREM api/worker MI for `Cognitive Services OpenAI User` |
| `key_vault_id` + `store_api_key_in_key_vault` | Optional fallback key storage (not recommended for production) |

See `variables.tf` and `terraform.tfvars.example`.

## Configuration

```bash
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars — placeholders only, no secrets in git
```

**Never commit** `terraform.tfvars` or API keys.

## Plan and apply

```bash
terraform fmt
terraform validate
terraform plan
terraform apply
```

## Outputs

After apply:

- `azure_openai_endpoint`
- `chat_deployment_name`
- `embedding_deployment_name`
- `embedding_dimensions`
- `azure_openai_api_version`
- `aqrem_backend_env` — non-secret map for Container Apps / App Service env

API keys are **not** exported. Use **managed identity** or Key Vault references.

## AQREM backend integration

Set on **api** and **worker** (same values):

| Terraform output | AQREM env var |
|------------------|---------------|
| `azure_openai_endpoint` | `AZURE_OPENAI_ENDPOINT` |
| `chat_deployment_name` | `AZURE_OPENAI_CHAT_DEPLOYMENT` |
| `embedding_deployment_name` | `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` |
| `azure_openai_api_version` | `AZURE_OPENAI_API_VERSION` |
| `embedding_dimensions` | `EMBEDDING_DIMENSIONS` |
| — | `LLM_PROVIDER=azure` |

**Authentication (production):**

1. Set `managed_identity_principal_id` in Terraform → grants **Cognitive Services OpenAI User** on the account.
2. Enable on the app: `AZURE_OPENAI_USE_MANAGED_IDENTITY=true` (no API key in env).
3. Optional dev fallback: `store_api_key_in_key_vault=true` and reference the secret from Container Apps — do not commit the key.

Restart **api** and **worker** after changing LLM env vars. Re-sync sources after switching from mock embeddings.

## Embedding dimension requirements

AQREM stores vectors in PostgreSQL **pgvector** with size `EMBEDDING_DIMENSIONS` at schema creation time.

| Mode | Typical dimensions |
|------|---------------------|
| Local mock (`LLM_PROVIDER=mock`) | **384** |
| Azure `text-embedding-3-small` | **1536** |
| Azure `text-embedding-3-large` | **3072** (if deployed) |

Terraform variable `embedding_dimensions` must match the **actual** embedding model output. Set the same value in AQREM env before creating the database, or migrate columns and **re-index all evidence**.

## Security notes

- No API keys in outputs, README, or frontend
- Prefer managed identity + RBAC over account keys
- Key Vault secret creation is optional and off by default
- Set `public_network_access_enabled = false` when private endpoints exist (not created here)
- Use separate `terraform.tfvars` per environment

## Cost notes (MVP)

- Single OpenAI account per environment
- `chat_capacity` and `embedding_capacity` default to **1** — increase only as needed
- Choose smaller chat models (e.g. `gpt-4o-mini`) for dev/staging
- No extra gateways, AKS, or duplicate accounts

## Production considerations

- Pin model **versions** in tfvars after validating in dev
- Store Terraform state remotely (Azure Storage + locking)
- Use MI on Container Apps; assign `managed_identity_principal_id` at apply time
- Document model version upgrades and re-index impact
- Align `APP_ENV=production` with `public_network_access_enabled` and network design

## Destroy

```bash
terraform destroy
```

For dev accounts, `purge_cognitive_account_on_destroy = true` avoids soft-delete name conflicts. **Do not** enable purge in production without review.

## What this module reuses

- Existing **resource group** (data source only)
- Optional existing **Key Vault** (secret write only)
- Optional existing **managed identity** (RBAC assignment only)

No duplicate OpenAI accounts are created unless you run this stack multiple times with different names/environments.

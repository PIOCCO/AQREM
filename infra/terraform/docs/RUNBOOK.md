# AQREM platform runbook (Stage 3)

## Pre-apply checklist

- [ ] Remote Terraform state storage: encrypted, private, RBAC-only (D11).
- [ ] **Separate dev subscription** for non-prod (D15).
- [ ] Request **Container Apps consumption core quota** per environment (default often 40; target 100+ for dense cells). Portal → Quotas → Azure Container Apps → *Managed Environment Consumption Cores*.
- [ ] Request **managed environment count** quota if running many cells + platform CAE.
- [ ] Set `clients_per_cell` (default **25**) from observed core usage.
- [ ] Verify **gpt-4.1-mini** / **text-embedding-3-small** in region ([region availability](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure-region-availability)).
- [ ] Upload **BYO wildcard** cert to platform Key Vault for `*.aqrem.app`; bind on Front Door custom domain.
- [ ] Configure **SPF/DKIM/DMARC** (`docs/EMAIL_DNS.md`).

## Deploy platform (no apply without approval)

```bash
cd infra/terraform/stacks/platform
terraform init
terraform validate
terraform plan -var-file=terraform.tfvars
```

## Deploy sample client

```bash
cd infra/terraform/stacks/client
terraform init
terraform validate
terraform plan -var-file=../../parameters/clients/acme.sample.tfvars.json
```

State key pattern: `clients/<clientId>.tfstate`.

## Control-plane PostgreSQL auth choice

**Chosen: Entra ID only** (`password_auth_enabled=false`). No PostgreSQL password in Terraform state.

- Bootstrap: grant **provisioning pipeline SP** temporary Entra admin via `platform_pg_bootstrap_entra_admin_object_id`.
- Runtime: **gateway managed identity** is **not** Entra admin. Apply `infra/platform/db/migrations/003_gateway_least_privilege_role.sql`, map MI via `pgaadauth_create_principal`, then `GRANT aqrem_gateway_app TO "<gw-mi>"`.
- Onboarding worker / product API use **`aqrem_platform_worker`** / **`aqrem_product_api`** roles (`005_platform_component_roles.sql`).
- Tenant PostgreSQL: **azurerm `administrator_password_wo`** (azurerm **≥4.21**, Terraform **≥1.11**) — the flexible-server password is **write-only** and not persisted in server state. A `random_password` still exists for Key Vault bootstrap during apply (protect with encrypted remote state). If write-only is unavailable, use `administrator_password` + encrypted private versioned state + `docs/TENANT_DB_PASSWORD_ROTATION.md`.

## Model migration (alias retarget)

1. Deploy new OpenAI model in platform stack (or update deployment SKU/version).
2. Point gateway alias (`chat-default`) to new deployment name in Container App env / config.
3. Run evaluation set in `docs/MODEL_EVAL_RAG.md` for pilot tenant.
4. Roll out via `update-clients` pipeline waves (10% → 50% → 100%) with automatic rollback.
5. Update runbook retirement tracker — **do not lock production** on models within **12 months** of retirement (see `gpt-4.1-mini` note below).

## Gateway alerts

- **Availability:** min **2** gateway replicas, zone-redundant CAE, `/health/live` + `/health/ready`.
- **Alert:** App Insights / LAW — gateway 5xx rate > 2% over 5m (configure action group in monitoring module when wired).
- **Client behavior:** `docs/GATEWAY_CLIENT_BEHAVIOR.md`.

## gpt-4.1-mini retirement

Azure documents **2027-10-14** retirement for `gpt-4.1-mini` — within **12 months** of Oct 2026, so it is **dev default only** until `MODEL_EVAL_RAG.md` compares **gpt-4.1-nano** and newer small GA models in **westeurope**. Check [model retirement](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/model-retirements) before production lock-in.

## Azure OpenAI pricing in docs

Use official [Azure OpenAI pricing](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/) for **westeurope** — third-party catalog prices in older notes are **unverified**.

## Front Door domain capacity

- **Standard:** **100 custom domains per profile** ([service limits](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/azure-subscription-service-limits#azure-front-door-standard-and-premium-service-limits)).
- Second profile needed when approaching **100 client hostnames** (or **100 routes**, same limit class).
- **Premium:** 500 custom domains per profile.

## Origin protection (Standard tier)

Restrict each client web Container App ingress to **service tag `AzureFrontDoor.Backend`** and validate header **`X-Azure-FDID`** = Front Door profile resource GUID.

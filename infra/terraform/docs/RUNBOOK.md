# AQREM platform runbook (Stage 2)

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
- Runtime: **gateway managed identity** is Entra admin for schema/tables; apps use per-client keys only at gateway layer.
- Tenant PostgreSQL (client stack) still uses generated passwords **stored only in client Key Vault** (password appears in Terraform state for that client stack — mitigate with encrypted remote state and `-target` pipelines).

## Front Door domain capacity

- **Standard:** **100 custom domains per profile** ([service limits](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/azure-subscription-service-limits#azure-front-door-standard-and-premium-service-limits)).
- Second profile needed when approaching **100 client hostnames** (or **100 routes**, same limit class).
- **Premium:** 500 custom domains per profile.

## Origin protection (Standard tier)

Restrict each client web Container App ingress to **service tag `AzureFrontDoor.Backend`** and validate header **`X-Azure-FDID`** = Front Door profile resource GUID.

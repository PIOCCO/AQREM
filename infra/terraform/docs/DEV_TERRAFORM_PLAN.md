# DEV subscription: Terraform plan checklist (Stage 1–3)

Run these in a **dedicated dev subscription**. Do **not** run `terraform apply` until you explicitly approve.

## Permissions and quotas to request first

| Need | Why |
|------|-----|
| **Contributor** (or custom provisioner role) on dev subscription | Create RGs, CAE, PG, ACR, OpenAI, Front Door |
| **User Access Administrator** (or role assignment rights) | Assign MI roles (AcrPull, OpenAI User, KV secrets) |
| **Microsoft.Authorization/roleAssignments/write** scoped to `aqrem-*` RGs | Provisioning pipeline OIDC SP |
| **Container Apps consumption cores** quota ≥ **100** per region | Platform gateway CAE + one cell CAE + 3 client apps |
| **Container Apps managed environments** quota ≥ **3** | Platform gateway + one cell (+ spare) |
| **PostgreSQL flexible servers** quota | 1 control-plane + 1 tenant |
| **Cognitive Services / OpenAI** quota in **westeurope** | Chat + embeddings deployments |
| **Front Door Standard** | 1 profile, 1 custom domain for sample client |
| **Key Vault** | Platform + client vaults |
| **Storage account** | Remote state (if not already provisioned) |

### Bootstrap identities

1. **Your user** (or break-glass group): temporary Entra admin on control-plane PG — set `platform_pg_bootstrap_entra_admin_object_id` to your user or a dev provisioning SP.
2. **GitHub Actions OIDC SP** (Stage 3): separate **dev** federated credential; prod uses manual approval (see `.github/workflows/onboard-client.yml`).

After first platform apply, run control-plane SQL migrations (`infra/platform/db/migrations/*.sql`) as bootstrap admin, then:

```sql
SELECT * FROM pgaadauth_create_principal('<platform-prefix>-gw-mi', false, false);
GRANT aqrem_gateway_app TO "<platform-prefix>-gw-mi";
```

## Remote state (recommended)

```bash
export ARM_SUBSCRIPTION_ID="<dev-subscription-id>"
export ARM_TENANT_ID="<tenant-id>"
az login
az account set --subscription "$ARM_SUBSCRIPTION_ID"
```

Create backend storage (once), then copy `backend.tf.example` → `backend.tf` for each stack and set `key`:

- Platform: `platform/dev.tfstate`
- Cell (if split): `cells/<cellId>/dev.tfstate`
- Client: `clients/<clientId>/dev.tfstate`

## 1) Platform stack plan

```bash
cd infra/terraform/stacks/platform
cp terraform.tfvars.example terraform.tfvars   # edit: environment=dev, subscription, bootstrap admin OID
terraform init
terraform fmt -check -recursive
terraform validate
terraform plan -var-file=terraform.tfvars -out=platform.dev.tfplan
```

Expected resources (high level): platform RG, VNet, NAT, control-plane PostgreSQL (private), ACR, platform KV + PE, LAW/App Insights, OpenAI account + deployments, custom gateway CA (≥2 replicas, zone redundant), optional Front Door profile.

## 2) One cell (embedded in client stack sample)

The sample **client stack** creates a **dedicated cell module** per deployment (`infra/terraform/stacks/client`). For a shared cell used by many clients, deploy `modules/cell` once and pass `container_app_environment_id` into client stacks (future pipeline).

## 3) Sample client plan

Edit `infra/terraform/parameters/clients/acme.sample.tfvars.json`:

- `tenant_id`, `subscription_id` (via env)
- `front_door_profile_id`, `front_door_endpoint_id` from platform outputs
- `registry_login_server` from platform ACR
- `gateway_url` from gateway Container App FQDN
- `postgresql_private_dns_zone_id` — reuse cell zone from platform/cell outputs
- `public_base_url` / `custom_domain_host` — e.g. `acme.dev.aqrem.app`

```bash
cd infra/terraform/stacks/client
terraform init
terraform validate
terraform plan -var-file=../../parameters/clients/acme.sample.tfvars.json -out=client-acme.dev.tfplan
```

## 4) Static IaC checks (same as CI)

```bash
cd infra/terraform
terraform fmt -check -recursive
for d in stacks/platform stacks/client .; do
  (cd "$d" && terraform init -backend=false && terraform validate)
done
# Optional locally:
# tflint --recursive
# checkov -d stacks/platform -d stacks/client --framework terraform
```

## Paste plan results

If you paste `terraform plan` output (redact subscription IDs if needed), we will:

- Flag unexpected destroys or public exposure
- Confirm SKU/region alignment with decisions
- Note missing quotas or provider errors

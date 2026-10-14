# AQREM shared platform (Terraform Stage 1)

Deploys the **shared platform** resource group:

- Azure Container Registry
- Platform Key Vault (RBAC, purge protection)
- Log Analytics + Application Insights
- Control-plane PostgreSQL (password → Key Vault only)
- Azure OpenAI (shared chat + embeddings)
- Model gateway (**APIM Standard v2**, not Consumption)
- Front Door Standard profile + endpoint + placeholder origin group + WAF policy

## Prerequisites

- Terraform >= 1.6, Azure CLI logged in
- Remote state storage (see `backend.tf.example`)
- **Do not apply** without explicit approval

## Commands

```bash
cd infra/terraform/stacks/platform
cp backend.tf.example backend.tf   # edit
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform validate
terraform plan -var-file=terraform.tfvars
```

## Post-apply (manual / Stage 2)

- Wire APIM policies (`llm-token-limit`, backend to OpenAI)
- Register client origins on Front Door per onboarding
- Store Brevo API key in platform Key Vault (`brevo-api-key`)
- BYO wildcard cert in Key Vault for `*.aqrem.app` if using wildcard TLS

See `../../docs/AZURE_VERIFICATION_2026-10.md` for October 2026 Azure checks.

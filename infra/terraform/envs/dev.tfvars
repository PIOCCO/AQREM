# AQREM Azure OpenAI — dev. No secrets in this file (it is committed).
# Subscription comes from `az account set` / ARM_SUBSCRIPTION_ID, not from here.
environment         = "dev"
location            = "swedencentral"
resource_group_name = "rg-aqrem-dev" # must already exist (this stack does not create RGs)

# Account / subdomain: aoai-aqrem-dev-<name_suffix>.openai.azure.com — set once, never change.
name_suffix = "sc01"

# Cheapest pay-per-token type. GlobalStandard may process prompts in ANY Azure region.
deployment_sku_name = "GlobalStandard"

chat_model_name      = "gpt-4o-mini"
chat_model_version   = "2024-07-18" # Deprecated (existing customers only), retires 2027-04-14 — see docs/azure-terraform.md
chat_deployment_name = "aqrem-chat"
chat_capacity        = 10 # 10K TPM rate limit (quota), not a spending cap

embedding_model_name      = "text-embedding-3-small"
embedding_model_version   = "1"
embedding_deployment_name = "aqrem-embeddings"
embedding_capacity        = 30 # 30K TPM; raise temporarily for bulk re-indexing
embedding_dimensions      = 1536

version_upgrade_option = "OnceCurrentVersionExpired"

# The Raspberry Pi cannot use managed identity, so dev keeps API keys enabled.
local_auth_enabled = true

public_network_access_enabled = true
# Optional: lock the endpoint to the Pi's/your static egress IP.
# network_acls_default_action = "Deny"
# allowed_ip_rules            = ["203.0.113.10"]

enable_delete_lock                 = false
purge_cognitive_account_on_destroy = true # dev only: frees the name immediately on destroy

# managed_identity_principal_id = "<object-id-of-app-identity>"
# log_analytics_workspace_id    = "/subscriptions/.../workspaces/..."

tags = { CostCenter = "aqrem-dev" }

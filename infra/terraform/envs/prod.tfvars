# AQREM Azure OpenAI — production. No secrets in this file (it is committed).
environment         = "production"
location            = "swedencentral"
resource_group_name = "rg-aqrem-prod" # must already exist

name_suffix = "sc01"

# EU data residency for processing: DataZoneStandard keeps inference inside the EU data zone
# (about +10% vs GlobalStandard). Use "Standard" for chat only if you need in-region processing;
# text-embedding-3-small has NO regional Standard offer in swedencentral.
deployment_sku_name = "DataZoneStandard"

chat_model_name      = "gpt-4o-mini"
chat_model_version   = "2024-07-18" # Deprecated, retires 2027-04-14; plan a migration (see docs)
chat_deployment_name = "aqrem-chat"
chat_capacity        = 30 # 30K TPM / ~180 RPM rate limit; check quota with az cognitiveservices usage list

embedding_model_name      = "text-embedding-3-small"
embedding_model_version   = "1"
embedding_deployment_name = "aqrem-embeddings"
embedding_capacity        = 100 # 100K TPM for indexing bursts; quota only, billed per token
embedding_dimensions      = 1536

version_upgrade_option = "OnceCurrentVersionExpired"

# Entra ID only. The app must run in Azure with AZURE_OPENAI_USE_MANAGED_IDENTITY=true.
# Set to true ONLY if a key-based client (e.g. the Raspberry Pi) must call production.
local_auth_enabled = false
# managed_identity_principal_id = "<object-id-of-api/worker-managed-identity>"

# Recommended: false + private endpoint (not created by this stack). Until the app runs inside a
# VNet, keep public access but restrict it to known egress IPs.
public_network_access_enabled = true
network_acls_default_action   = "Deny"
allowed_ip_rules              = [] # add the app's egress IP(s) before apply, or every call is 403

enable_delete_lock                 = true
purge_cognitive_account_on_destroy = false

# log_analytics_workspace_id = "/subscriptions/.../workspaces/..."

tags = { CostCenter = "aqrem-prod" }

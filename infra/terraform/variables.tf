variable "subscription_id" {
  type        = string
  description = "Azure subscription ID. Omit when using Azure CLI default context (ARM_SUBSCRIPTION_ID)."
  default     = null
  nullable    = true
}

variable "project_name" {
  type        = string
  description = "Short project slug used in resource names."
  default     = "aqrem"

  validation {
    condition     = can(regex("^[a-z0-9-]{2,20}$", var.project_name))
    error_message = "project_name must be 2–20 lowercase letters, numbers, or hyphens."
  }
}

variable "environment" {
  type        = string
  description = "Deployment environment (dev, staging, production)."

  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "environment must be one of: dev, staging, production."
  }
}

variable "location" {
  type        = string
  description = "Azure region for the Azure OpenAI account (must support chosen models)."
}

variable "resource_group_name" {
  type        = string
  description = "Existing resource group name (not created by this module)."
}

variable "openai_account_name" {
  type        = string
  description = "Explicit Azure OpenAI account name, also used as the globally unique custom subdomain (<name>.openai.azure.com). Default: aoai-<project_name>-<environment>[-<name_suffix>]. Changing it REPLACES the account (new endpoint, deployments recreated)."
  default     = null
  nullable    = true

  validation {
    condition     = var.openai_account_name == null || can(regex("^[a-zA-Z0-9][a-zA-Z0-9-]{0,62}[a-zA-Z0-9]$", var.openai_account_name))
    error_message = "openai_account_name must be 2-64 characters: alphanumerics and hyphens, starting and ending with an alphanumeric."
  }
}

variable "name_suffix" {
  type        = string
  description = "Optional short, stable suffix appended to the default account name to make the global subdomain unique (e.g. \"sc01\"). Deterministic replacement for a random_string; set once and never change it (a change replaces the account)."
  default     = null
  nullable    = true

  validation {
    condition     = var.name_suffix == null || can(regex("^[a-z0-9]{1,8}$", var.name_suffix))
    error_message = "name_suffix must be 1-8 lowercase letters or digits."
  }
}

variable "openai_sku_name" {
  type        = string
  description = "Cognitive Services account SKU. Azure OpenAI accounts only offer S0 (no charge for the account itself; billing is per deployment usage)."
  default     = "S0"

  validation {
    condition     = var.openai_sku_name == "S0"
    error_message = "Azure OpenAI accounts support sku_name S0 only."
  }
}

variable "public_network_access_enabled" {
  type        = bool
  description = "Allow access over the public endpoint (HTTPS only; Azure OpenAI has no HTTP listener). dev: true, optionally narrowed with allowed_ip_rules. production: prefer false + a private endpoint (not created by this stack; see docs/azure-terraform.md)."
  default     = true
}

variable "network_acls_default_action" {
  type        = string
  description = "Network ACL default action when public access is enabled. Use Deny together with allowed_ip_rules to allow only listed IPs (e.g. the Raspberry Pi's static egress IP)."
  default     = "Allow"

  validation {
    condition     = contains(["Allow", "Deny"], var.network_acls_default_action)
    error_message = "network_acls_default_action must be Allow or Deny."
  }
}

variable "allowed_ip_rules" {
  type        = list(string)
  description = "Public IPv4 addresses or CIDR ranges allowed when network_acls_default_action = Deny. No secrets; but treat as infra metadata."
  default     = []

  validation {
    condition     = alltrue([for ip in var.allowed_ip_rules : can(cidrhost(strcontains(ip, "/") ? ip : "${ip}/32", 0))])
    error_message = "Each allowed_ip_rules entry must be an IPv4 address or CIDR."
  }
}

variable "local_auth_enabled" {
  type        = bool
  description = "Allow API-key auth. Set false in production to force Microsoft Entra ID (managed identity / service principal with Cognitive Services OpenAI User). Keep true only where the app cannot use Entra ID (e.g. the Raspberry Pi)."
  default     = true
}

variable "outbound_network_access_restricted" {
  type        = bool
  description = "Block the account's own outbound calls (data-exfiltration control). Safe for AQREM, which only uses chat/embeddings; breaks features like 'on your data'."
  default     = true
}

variable "system_assigned_identity_enabled" {
  type        = bool
  description = "Enable a system-assigned managed identity on the Azure OpenAI account (needed for customer-managed keys or calling other Azure resources; harmless otherwise)."
  default     = true
}

variable "enable_delete_lock" {
  type        = bool
  description = "Create a CanNotDelete management lock on the account (recommended for production). Blocks terraform destroy and deployment deletion until removed."
  default     = false
}

variable "log_analytics_workspace_id" {
  type        = string
  description = "Optional Log Analytics workspace ID for Audit logs + AllMetrics. No request/response content is logged."
  default     = null
  nullable    = true
}

variable "version_upgrade_option" {
  type        = string
  description = "Model version auto-upgrade policy for both deployments: OnceCurrentVersionExpired (stay pinned until retirement), OnceNewDefaultVersionAvailable, or NoAutoUpgrade (deployment stops working at retirement)."
  default     = "OnceCurrentVersionExpired"

  validation {
    condition     = contains(["OnceCurrentVersionExpired", "OnceNewDefaultVersionAvailable", "NoAutoUpgrade"], var.version_upgrade_option)
    error_message = "version_upgrade_option must be OnceCurrentVersionExpired, OnceNewDefaultVersionAvailable or NoAutoUpgrade."
  }
}

variable "deployment_sku_name" {
  type        = string
  description = "Default deployment type for both deployments (overridable per deployment). Standard = regional processing; DataZoneStandard = processing within the EU data zone; GlobalStandard = any region (cheapest). NOTE: text-embedding-3-small is NOT offered as regional Standard in swedencentral."
  default     = "GlobalStandard"

  validation {
    condition     = contains(local.allowed_deployment_skus, var.deployment_sku_name)
    error_message = "deployment_sku_name must be one of Standard, GlobalStandard, DataZoneStandard, ProvisionedManaged, GlobalProvisionedManaged, DataZoneProvisionedManaged."
  }
}

variable "chat_deployment_sku_name" {
  type        = string
  description = "Deployment type for the chat deployment; null = deployment_sku_name."
  default     = null
  nullable    = true

  validation {
    condition     = var.chat_deployment_sku_name == null || contains(local.allowed_deployment_skus, coalesce(var.chat_deployment_sku_name, "x"))
    error_message = "chat_deployment_sku_name must be null or a supported deployment type."
  }
}

variable "embedding_deployment_sku_name" {
  type        = string
  description = "Deployment type for the embedding deployment; null = deployment_sku_name."
  default     = null
  nullable    = true

  validation {
    condition     = var.embedding_deployment_sku_name == null || contains(local.allowed_deployment_skus, coalesce(var.embedding_deployment_sku_name, "x"))
    error_message = "embedding_deployment_sku_name must be null or a supported deployment type."
  }
}

variable "chat_model_name" {
  type        = string
  description = "Azure OpenAI chat model name (e.g. gpt-4o-mini)."
}

variable "chat_model_version" {
  type        = string
  description = "Model version string from Azure OpenAI model catalog for the region."
}

variable "chat_deployment_name" {
  type        = string
  description = "Deployment name for chat completions (maps to AZURE_OPENAI_CHAT_DEPLOYMENT)."
}

variable "chat_capacity" {
  type        = number
  description = "Chat deployment capacity. For Standard/GlobalStandard/DataZoneStandard: 1 unit = 1,000 tokens-per-minute rate limit (consumes subscription quota; it is NOT a budget, you pay per token). For *Provisioned* SKUs it is PTUs (billed hourly)."
  default     = 1

  validation {
    condition     = var.chat_capacity >= 1
    error_message = "chat_capacity must be at least 1."
  }
}

variable "embedding_model_name" {
  type        = string
  description = "Azure OpenAI embedding model name (e.g. text-embedding-3-small)."
}

variable "embedding_model_version" {
  type        = string
  description = "Embedding model version from Azure OpenAI model catalog."
}

variable "embedding_deployment_name" {
  type        = string
  description = "Deployment name for embeddings (maps to AZURE_OPENAI_EMBEDDING_DEPLOYMENT)."
}

variable "embedding_capacity" {
  type        = number
  description = "Embedding deployment capacity (1 unit = 1,000 TPM for standard deployment types; quota, not a budget)."
  default     = 1

  validation {
    condition     = var.embedding_capacity >= 1
    error_message = "embedding_capacity must be at least 1."
  }
}

variable "embedding_dimensions" {
  type        = number
  description = <<-EOT
    Vector dimensions produced by the embedding deployment. Must match AQREM EMBEDDING_DIMENSIONS
    and PostgreSQL pgvector column size. For text-embedding-3-small this is typically 1536.
    Mock local dev uses 384 — do not use 384 in production Azure deployments.
  EOT

  validation {
    condition     = contains([512, 1024, 1536, 3072], var.embedding_dimensions)
    error_message = "embedding_dimensions must match the deployed Azure embedding model (common: 1536 for text-embedding-3-small). Mock 384 is not valid for this Terraform stack."
  }
}

variable "azure_openai_api_version" {
  type        = string
  description = "Azure OpenAI REST api-version used by AQREM (maps to AZURE_OPENAI_API_VERSION)."
  default     = "2024-10-21"
}

variable "key_vault_id" {
  type        = string
  description = "Optional existing Key Vault resource ID. When set with store_api_key_in_key_vault, stores the account key as a secret (fallback for non-MI workloads)."
  default     = null
  nullable    = true
}

variable "store_api_key_in_key_vault" {
  type        = bool
  description = "Store the account primary key in Key Vault via Terraform. Discouraged: the key value is then also stored in Terraform state. Prefer Entra ID, or copy the key manually (docs/azure-terraform.md)."
  default     = false

  validation {
    condition     = !(var.store_api_key_in_key_vault && !var.local_auth_enabled)
    error_message = "store_api_key_in_key_vault requires local_auth_enabled = true (keys are disabled otherwise)."
  }
}

variable "key_vault_secret_name" {
  type        = string
  description = "Secret name for the optional stored API key."
  default     = "aqrem-azure-openai-api-key"
}

variable "managed_identity_principal_id" {
  type        = string
  description = "Object (principal) ID of the AQREM api/worker managed identity or service principal. Granted 'Cognitive Services OpenAI User' (inference only) on the account. Not a secret."
  default     = null
  nullable    = true
}

variable "assign_openai_user_role" {
  type        = bool
  description = "Grant Cognitive Services OpenAI User on the OpenAI account to managed_identity_principal_id."
  default     = true
}

variable "tags" {
  type        = map(string)
  description = "Additional resource tags merged with standard AQREM tags."
  default     = {}
}

variable "purge_cognitive_account_on_destroy" {
  type        = bool
  description = "Purge soft-deleted cognitive account on terraform destroy (dev only)."
  default     = false
}

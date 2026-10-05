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
  description = "Globally unique Azure OpenAI account name. Default: aoai-<project_name>-<environment>."
  default     = null
  nullable    = true
}

variable "openai_sku_name" {
  type        = string
  description = "Cognitive Services SKU for the OpenAI account."
  default     = "S0"
}

variable "public_network_access_enabled" {
  type        = bool
  description = "When false, public internet access to the account is disabled (use with private endpoints when available)."
  default     = true
}

variable "deployment_sku_name" {
  type        = string
  description = "SKU name for model deployments (typically Standard)."
  default     = "Standard"
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
  description = "PTU/token capacity units for the chat deployment (MVP: start low)."
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
  description = "Capacity units for the embedding deployment."
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
  description = "Store the Azure OpenAI account primary key in Key Vault. Prefer managed identity for production API/worker."
  default     = false
}

variable "key_vault_secret_name" {
  type        = string
  description = "Secret name for the optional stored API key."
  default     = "aqrem-azure-openai-api-key"
}

variable "managed_identity_principal_id" {
  type        = string
  description = "Principal ID of AQREM api/worker user-assigned or system-assigned managed identity for Cognitive Services OpenAI User role."
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

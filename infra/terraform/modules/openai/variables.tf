variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "openai_account_name" {
  type = string
}

variable "openai_sku_name" {
  type    = string
  default = "S0"
}

variable "public_network_access_enabled" {
  type    = bool
  default = true
}

variable "deployment_sku_name" {
  type    = string
  default = "Standard"
}

variable "chat_model_name" {
  type = string
}

variable "chat_model_version" {
  type = string
}

variable "chat_deployment_name" {
  type = string
}

variable "chat_capacity" {
  type    = number
  default = 1
}

variable "embedding_model_name" {
  type = string
}

variable "embedding_model_version" {
  type = string
}

variable "embedding_deployment_name" {
  type = string
}

variable "embedding_capacity" {
  type    = number
  default = 1
}

variable "embedding_dimensions" {
  type = number
}

variable "azure_openai_api_version" {
  type    = string
  default = "2024-10-21"
}

variable "key_vault_id" {
  type     = string
  default  = null
  nullable = true
}

variable "store_api_key_in_key_vault" {
  type    = bool
  default = false
}

variable "key_vault_secret_name" {
  type    = string
  default = "aqrem-azure-openai-api-key"
}

variable "managed_identity_principal_id" {
  type     = string
  default  = null
  nullable = true
}

variable "assign_openai_user_role" {
  type    = bool
  default = true
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "purge_cognitive_account_on_destroy" {
  type    = bool
  default = false
}

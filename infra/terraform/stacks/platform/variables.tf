variable "subscription_id" {
  type     = string
  default  = null
  nullable = true
}

variable "project_name" {
  type    = string
  default = "aqrem"
}

variable "environment" {
  type = string

  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "environment must be dev, staging, or production."
  }
}

variable "location" {
  type    = string
  default = "westeurope"
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "publisher_email" {
  type        = string
  description = "APIM publisher contact email (when enable_apim=true)."
}

variable "enable_apim" {
  type        = bool
  default     = false
  description = "Defer ~$700/mo APIM Standard v2 until scale/compliance requires it."
}

variable "enable_custom_gateway" {
  type    = bool
  default = true
}

variable "deploy_front_door" {
  type    = bool
  default = true
}

variable "deploy_openai" {
  type    = bool
  default = true
}

variable "clients_per_cell" {
  type        = number
  default     = 25
  description = "Soft pack limit per cell; request ACA core quota increase in runbook when scaling."
}

variable "apim_sku_name" {
  type    = string
  default = "StandardV2_1"
}

variable "front_door_sku_name" {
  type    = string
  default = "Standard_AzureFrontDoor"
}

variable "acr_sku" {
  type    = string
  default = "Basic"
}

variable "control_plane_postgres_sku" {
  type    = string
  default = "B_Standard_B1ms"
}

variable "gateway_container_image" {
  type    = string
  default = "aqremprodacr.azurecr.io/aqrem-model-gateway:latest"
}

variable "gateway_zone_redundant" {
  type    = bool
  default = true
}

variable "gateway_internal_provisioning_token" {
  type      = string
  default   = null
  nullable  = true
  sensitive = true
}

variable "platform_pg_bootstrap_entra_admin_object_id" {
  type        = string
  default     = null
  nullable    = true
  description = "Provisioning pipeline SP object id for bootstrap PG admin (runs SQL migrations and role grants)."
}

variable "platform_pg_bootstrap_entra_admin_name" {
  type    = string
  default = "aqrem-provisioner"
}

variable "azure_openai_api_version" {
  type    = string
  default = "2024-10-21"
}

variable "chat_model_name" {
  type    = string
  default = "gpt-4.1-mini"
}

variable "chat_model_version" {
  type    = string
  default = "2025-04-14"
}

variable "chat_deployment_name" {
  type    = string
  default = "aqrem-chat"
}

variable "embedding_model_name" {
  type    = string
  default = "text-embedding-3-small"
}

variable "embedding_model_version" {
  type    = string
  default = "1"
}

variable "embedding_deployment_name" {
  type    = string
  default = "aqrem-embeddings"
}

variable "embedding_dimensions" {
  type    = number
  default = 1536
}

variable "chat_capacity" {
  type    = number
  default = 10
}

variable "embedding_capacity" {
  type    = number
  default = 10
}

variable "openai_public_network_access_enabled" {
  type    = bool
  default = true
}

variable "gateway_managed_identity_principal_id" {
  type     = string
  default  = null
  nullable = true
}

variable "purge_cognitive_account_on_destroy" {
  type    = bool
  default = false
}

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
  description = "APIM publisher contact email."
}

variable "deploy_model_gateway" {
  type        = bool
  default     = true
  description = "Set false for dev cost savings; clients cannot reach OpenAI without an alternate gateway."
}

variable "deploy_front_door" {
  type    = bool
  default = true
}

variable "deploy_openai" {
  type    = bool
  default = true
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
  type        = string
  default     = null
  nullable    = true
  description = "Principal ID for APIM/system MI to grant Cognitive Services OpenAI User (configure after APIM identity exists)."
}

variable "purge_cognitive_account_on_destroy" {
  type    = bool
  default = false
}

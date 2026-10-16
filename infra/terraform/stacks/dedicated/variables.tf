# --- The short parameter list for a new dedicated client ---------------------------------
variable "client" {
  type        = string
  description = "Client id, e.g. contoso (lowercase, 3-20 chars)."
}

variable "location" {
  type        = string
  description = "Azure region, e.g. westeurope."
}

variable "size" {
  type        = string
  default     = "small"
  description = "small | medium | large."
}

variable "db_mode" {
  type        = string
  default     = "new"
  description = "new = new PostgreSQL Flexible Server; existing = existing_database_url."
}

variable "existing_database_url" {
  type      = string
  default   = null
  nullable  = true
  sensitive = true
  ephemeral = true
}

variable "existing_migration_database_url" {
  type      = string
  default   = null
  nullable  = true
  sensitive = true
  ephemeral = true
}

# --- Platform-wide values (same for every client; set once in a shared tfvars) ------------
variable "subscription_id" {
  type     = string
  default  = null
  nullable = true
}

variable "tenant_id" {
  type = string
}

variable "registry_login_server" {
  type = string
}

variable "acr_id" {
  type     = string
  default  = null
  nullable = true
}

variable "image_tag" {
  type = string
}

variable "organization_name" {
  type    = string
  default = ""
}

variable "openai_account_id" {
  type     = string
  default  = null
  nullable = true
}

variable "openai_endpoint" {
  type    = string
  default = ""
}

variable "openai_chat_deployment" {
  type    = string
  default = "chat"
}

variable "openai_embedding_deployment" {
  type    = string
  default = "embeddings"
}

variable "document_intelligence_account_id" {
  type     = string
  default  = null
  nullable = true
}

variable "document_intelligence_endpoint" {
  type    = string
  default = ""
}

variable "vnet_address_space" {
  type    = string
  default = "10.210.0.0/16"
}

variable "deployer_ip_cidrs" {
  type    = list(string)
  default = []
}

variable "secrets_version" {
  type    = number
  default = 1
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "existing_has_migration_url" {
  type        = bool
  default     = false
  description = "existing db_mode: true when existing_migration_database_url (owner role) is supplied."
}

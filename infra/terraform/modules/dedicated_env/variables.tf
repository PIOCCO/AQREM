variable "client" {
  type        = string
  description = "Short client id (lowercase letters, digits, dashes; 3-20 chars)."

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,19}$", var.client))
    error_message = "client must match ^[a-z][a-z0-9-]{2,19}$."
  }
}

variable "location" {
  type = string
}

variable "size" {
  type    = string
  default = "small"

  validation {
    condition     = contains(["small", "medium", "large"], var.size)
    error_message = "size must be small, medium or large."
  }
}

variable "resource_group_name" {
  type = string
}

variable "tenant_id" {
  type = string
}

variable "vnet_id" {
  type = string
}

variable "subnet_private_endpoints_id" {
  type = string
}

variable "subnet_postgresql_id" {
  type = string
}

variable "container_app_environment_id" {
  type = string
}

variable "db_mode" {
  type        = string
  default     = "new"
  description = "new = create PostgreSQL Flexible Server; existing = use existing_database_url."

  validation {
    condition     = contains(["new", "existing"], var.db_mode)
    error_message = "db_mode must be new or existing."
  }
}

variable "existing_database_url" {
  type        = string
  default     = null
  nullable    = true
  sensitive   = true
  ephemeral   = true
  description = "Least-privilege app role URL (postgresql+psycopg://...?...sslmode=require). Write-only into Key Vault."
}

variable "existing_migration_database_url" {
  type      = string
  default   = null
  nullable  = true
  sensitive = true
  ephemeral = true
}

variable "secrets_version" {
  type        = number
  default     = 1
  description = "Bump to re-write the write-only Key Vault secrets (rotation)."
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
  type        = string
  description = "Release tag used for api/worker/web images (also reported as APP_VERSION)."
}

variable "image_name_api" {
  type    = string
  default = "aqrem-api"
}

variable "image_name_worker" {
  type    = string
  default = "aqrem-worker"
}

variable "image_name_web" {
  type    = string
  default = "aqrem-web"
}

variable "organization_name" {
  type    = string
  default = ""
}

variable "openai_account_id" {
  type        = string
  default     = null
  nullable    = true
  description = "Existing Azure OpenAI account resource id (private endpoint + RBAC are created)."
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

variable "deployer_ip_cidrs" {
  type        = list(string)
  default     = []
  description = "Operator IPs allowed through the Key Vault firewall so Terraform can write secrets. Empty = private only."
}

variable "public_base_url" {
  type    = string
  default = ""
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "redis_image" {
  type        = string
  default     = ""
  description = "Redis image; default <registry>/redis:7-alpine (mirror it into your ACR so no public registry is used)."
}

variable "existing_has_migration_url" {
  type        = bool
  default     = false
  description = "existing db_mode: true when existing_migration_database_url (owner role) is supplied."
}

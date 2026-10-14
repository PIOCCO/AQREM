variable "server_name" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "delegated_subnet_id" {
  type = string
}

variable "private_dns_zone_id" {
  type = string
}

variable "tenant_id" {
  type = string
}

variable "entra_auth_enabled" {
  type    = bool
  default = true
}

variable "password_auth_enabled" {
  type        = bool
  default     = false
  description = "Keep false in production; Entra-only avoids passwords in Terraform state."
}

variable "allow_public_firewall_bootstrap" {
  type        = bool
  default     = false
  description = "Never in prod. Ignored when public_network_access_enabled is false."
}

variable "entra_admin_principal_ids" {
  type = map(object({
    object_id      = string
    principal_name = string
    principal_type = string
  }))
  default = {}
}

variable "administrator_login" {
  type    = string
  default = "aqremcp"
}

variable "database_name" {
  type    = string
  default = "aqrem_control"
}

variable "sku_name" {
  type    = string
  default = "B_Standard_B1ms"
}

variable "storage_mb" {
  type    = number
  default = 32768
}

variable "backup_retention_days" {
  type    = number
  default = 7
}

variable "postgres_version" {
  type    = string
  default = "16"
}

variable "zone" {
  type    = string
  default = "1"
}

variable "high_availability_mode" {
  type     = string
  default  = null
  nullable = true
}

variable "key_vault_id" {
  type     = string
  default  = null
  nullable = true
}

variable "key_vault_secret_name" {
  type    = string
  default = "platform-postgresql-admin-password"
}

variable "tags" {
  type    = map(string)
  default = {}
}

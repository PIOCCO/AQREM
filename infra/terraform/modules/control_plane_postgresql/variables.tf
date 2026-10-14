variable "server_name" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
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

variable "public_network_access_enabled" {
  type        = bool
  default     = true
  description = "Stage 1 bootstrap; disable when private subnet is wired (Stage 2 cells)."
}

variable "high_availability_mode" {
  type        = string
  default     = null
  nullable    = true
  description = "SameZone or ZoneRedundant when enabled."
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

variable "connection_string_secret_name" {
  type    = string
  default = "platform-postgresql-connection-string"
}

variable "tags" {
  type    = map(string)
  default = {}
}

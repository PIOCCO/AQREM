variable "client_id" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "environment" {
  type = string
}

variable "plan" {
  type = string
}

variable "tenant_id" {
  type = string
}

variable "cost_center" {
  type    = string
  default = "unassigned"
}

variable "owner" {
  type    = string
  default = "platform"
}

variable "key_vault_name" {
  type = string
}

variable "storage_account_name" {
  type = string
}

variable "storage_replication" {
  type    = string
  default = "LRS"
}

variable "blob_soft_delete_days" {
  type    = number
  default = 7
}

variable "db_mode" {
  type = string

  validation {
    condition     = contains(["managed", "byo"], var.db_mode)
    error_message = "db_mode must be managed or byo."
  }
}

variable "postgresql_server_name" {
  type    = string
  default = null
  nullable = true
}

variable "postgresql_database_name" {
  type    = string
  default = "aqrem_tenant"
}

variable "postgresql_sku_name" {
  type    = string
  default = "B_Standard_B1ms"
}

variable "postgresql_storage_mb" {
  type    = number
  default = 32768
}

variable "postgresql_backup_retention_days" {
  type    = number
  default = 7
}

variable "postgresql_subnet_id" {
  type     = string
  default  = null
  nullable = true
}

variable "postgresql_private_dns_zone_id" {
  type     = string
  default  = null
  nullable = true
}

variable "container_app_environment_id" {
  type = string
}

variable "registry_login_server" {
  type = string
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

variable "image_tag_api" {
  type = string
}

variable "image_tag_worker" {
  type = string
}

variable "image_tag_web" {
  type = string
}

variable "gateway_url" {
  type = string
}

variable "gateway_api_key_placeholder" {
  type      = string
  default   = "replace-after-onboard"
  sensitive = true
}

variable "public_base_url" {
  type = string
}

variable "queue_type" {
  type    = string
  default = "storage"
}

variable "api_min_replicas" {
  type    = number
  default = 0
}

variable "api_max_replicas" {
  type    = number
  default = 2
}

variable "api_cpu" {
  type    = number
  default = 0.5
}

variable "api_memory" {
  type    = string
  default = "1Gi"
}

variable "worker_min_replicas" {
  type    = number
  default = 0
}

variable "worker_max_replicas" {
  type    = number
  default = 3
}

variable "worker_cpu" {
  type    = number
  default = 0.5
}

variable "worker_memory" {
  type    = string
  default = "1Gi"
}

variable "web_min_replicas" {
  type    = number
  default = 1
}

variable "web_max_replicas" {
  type    = number
  default = 2
}

variable "web_cpu" {
  type    = number
  default = 0.25
}

variable "web_memory" {
  type    = string
  default = "0.5Gi"
}

variable "monthly_budget_usd" {
  type    = number
  default = 200
}

variable "budget_start_date" {
  type    = string
  default = "2026-01-01T00:00:00Z"
}

variable "budget_alert_emails" {
  type    = list(string)
  default = []
}

variable "tags" {
  type    = map(string)
  default = {}
}

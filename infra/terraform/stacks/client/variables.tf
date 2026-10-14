variable "subscription_id" {
  type     = string
  default  = null
  nullable = true
}

variable "client_id" {
  type = string
}

variable "cell_id" {
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

variable "cell_resource_group_name" {
  type = string
}

variable "client_resource_group_name" {
  type = string
}

variable "key_vault_name" {
  type = string
}

variable "storage_account_name" {
  type = string
}

variable "db_mode" {
  type    = string
  default = "managed"
}

variable "postgresql_server_name" {
  type = string
}

variable "postgresql_private_dns_zone_id" {
  type = string
}

variable "registry_login_server" {
  type = string
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

variable "public_base_url" {
  type = string
}

variable "clients_per_cell" {
  type    = number
  default = 25
}

variable "enable_front_door_route" {
  type    = bool
  default = true
}

variable "front_door_profile_id" {
  type     = string
  default  = null
  nullable = true
}

variable "front_door_endpoint_id" {
  type     = string
  default  = null
  nullable = true
}

variable "custom_domain_host" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}

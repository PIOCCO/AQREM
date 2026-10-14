variable "identity_name" {
  type = string
}

variable "container_app_environment_name" {
  type = string
}

variable "container_app_name" {
  type = string
}

variable "location" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "infrastructure_subnet_id" {
  type = string
}

variable "internal_load_balancer_enabled" {
  type    = bool
  default = false
}

variable "registry_login_server" {
  type = string
}

variable "container_image" {
  type = string
}

variable "min_replicas" {
  type    = number
  default = 2
}

variable "max_replicas" {
  type    = number
  default = 5
}

variable "cpu" {
  type    = number
  default = 0.5
}

variable "memory" {
  type    = string
  default = "1Gi"
}

variable "azure_openai_endpoint" {
  type = string
}

variable "azure_openai_api_version" {
  type    = string
  default = "2024-10-21"
}

variable "openai_account_id" {
  type     = string
  default  = null
  nullable = true
}

variable "deployment_name_chat" {
  type = string
}

variable "deployment_name_embeddings" {
  type = string
}

variable "deployment_alias_chat" {
  type    = string
  default = "chat-default"
}

variable "deployment_alias_embeddings" {
  type    = string
  default = "embeddings-default"
}

variable "control_plane_postgresql_host" {
  type = string
}

variable "control_plane_database_name" {
  type    = string
  default = "aqrem_control"
}

variable "applicationinsights_connection_string" {
  type      = string
  default   = null
  nullable  = true
  sensitive = true
}

variable "ingress_external" {
  type    = bool
  default = true
}

variable "tags" {
  type    = map(string)
  default = {}
}

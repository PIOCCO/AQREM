variable "cell_id" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "create_resource_group" {
  type    = bool
  default = true
}

variable "location" {
  type = string
}

variable "vnet_name" {
  type = string
}

variable "vnet_address_space" {
  type    = string
  default = "10.200.0.0/16"
}

variable "subnet_container_apps_prefix" {
  type    = string
  default = "10.200.0.0/23"
}

variable "subnet_private_endpoints_prefix" {
  type    = string
  default = "10.200.2.0/24"
}

variable "subnet_postgresql_prefix" {
  type    = string
  default = "10.200.3.0/24"
}

variable "container_app_environment_name" {
  type = string
}

variable "max_clients" {
  type        = number
  default     = 25
  description = "Soft capacity target; control plane tracks used/free against environment core quota."
}

variable "tags" {
  type    = map(string)
  default = {}
}

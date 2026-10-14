variable "name_prefix" {
  type = string
}

variable "vnet_name" {
  type = string
}

variable "location" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "address_space" {
  type    = list(string)
  default = ["10.100.0.0/16"]
}

variable "subnet_postgresql_prefix" {
  type    = string
  default = "10.100.1.0/24"
}

variable "subnet_container_apps_prefix" {
  type    = string
  default = "10.100.2.0/23"
}

variable "subnet_private_endpoints_prefix" {
  type    = string
  default = "10.100.4.0/24"
}

variable "enable_nat_gateway" {
  type    = bool
  default = true
}

variable "tags" {
  type    = map(string)
  default = {}
}

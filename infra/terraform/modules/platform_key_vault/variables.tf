variable "name" {
  type = string
}

variable "location" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "soft_delete_retention_days" {
  type    = number
  default = 90
}

variable "purge_protection_enabled" {
  type    = bool
  default = true
}

variable "grant_deployer_admin" {
  type        = bool
  default     = true
  description = "Grant Key Vault Administrator to the identity running Terraform (bootstrap only)."
}

variable "tags" {
  type    = map(string)
  default = {}
}

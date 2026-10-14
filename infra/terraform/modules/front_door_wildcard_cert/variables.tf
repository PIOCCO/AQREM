variable "front_door_profile_id" {
  type = string
}

variable "key_vault_certificate_id" {
  type        = string
  description = "Key Vault certificate version id for *.aqrem.app wildcard."
}

variable "wildcard_host_name" {
  type        = string
  description = "e.g. *.aqrem.app or a managed apex pattern per Front Door rules."
}

variable "secret_name" {
  type    = string
  default = "wildcard-tls"
}

variable "custom_domain_resource_name" {
  type    = string
  default = "wildcard-aqrem-app"
}

variable "client_id" {
  type = string
}

variable "front_door_profile_id" {
  type = string
}

variable "front_door_endpoint_id" {
  type = string
}

variable "origin_host_name" {
  type = string
}

variable "custom_domain_host" {
  type = string
}

variable "certificate_type" {
  type        = string
  default     = "CustomerCertificate"
  description = "Use CustomerCertificate with BYO wildcard from platform Key Vault."
}

variable "health_probe_path" {
  type    = string
  default = "/"
}

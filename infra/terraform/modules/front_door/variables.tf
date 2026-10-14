variable "resource_group_name" {
  type = string
}

variable "profile_name" {
  type = string
}

variable "endpoint_name" {
  type = string
}

variable "origin_group_name" {
  type    = string
  default = "placeholder-origins"
}

variable "sku_name" {
  type    = string
  default = "Standard_AzureFrontDoor"
}

variable "response_timeout_seconds" {
  type    = number
  default = 120
}

variable "health_probe_path" {
  type    = string
  default = "/health/live"
}

variable "enable_waf" {
  type    = bool
  default = true
}

variable "waf_policy_name" {
  type    = string
  default = "aqremwaf"
}

variable "waf_mode" {
  type    = string
  default = "Prevention"
}

variable "tags" {
  type    = map(string)
  default = {}
}

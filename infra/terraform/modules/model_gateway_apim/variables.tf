variable "name" {
  type = string
}

variable "location" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "publisher_name" {
  type    = string
  default = "AQREM Platform"
}

variable "publisher_email" {
  type = string
}

variable "sku_name" {
  type        = string
  default     = "StandardV2_1"
  description = "Use StandardV2_1 for token quotas + streaming; not Consumption_0."
}

variable "virtual_network_type" {
  type        = string
  default     = "None"
  description = "None for bootstrap; External/Internal when subnet_id is set."
}

variable "subnet_id" {
  type        = string
  default     = null
  nullable    = true
  description = "APIM Standard v2 subnet for outbound VNet integration to private OpenAI."
}

variable "tags" {
  type    = map(string)
  default = {}
}

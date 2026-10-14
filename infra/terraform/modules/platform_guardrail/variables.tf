variable "policy_name" {
  type    = string
  default = "aqrem-prefix-region-guard"
}

variable "assignment_name" {
  type    = string
  default = "aqrem-guard-dev"
}

variable "resource_prefix" {
  type    = string
  default = "aqrem"
}

variable "allowed_locations" {
  type    = list(string)
  default = ["westeurope", "northeurope"]
}

variable "exempt_resource_types" {
  type = list(string)
  default = [
    "Microsoft.Authorization/roleAssignments",
    "Microsoft.Resources/deployments",
  ]
}

variable "subscription_id" {
  type = string
}

variable "assign_to_subscription" {
  type    = bool
  default = false
}

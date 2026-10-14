variable "role_name" {
  type    = string
  default = "AQREM Provisioner"
}

variable "principal_id" {
  type     = string
  default  = null
  nullable = true
}

variable "assignment_scope" {
  type     = string
  default  = null
  nullable = true
}

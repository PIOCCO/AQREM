variable "name" {
  type = string
}

variable "app_insights_name" {
  type = string
}

variable "location" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "retention_in_days" {
  type    = number
  default = 90
}

variable "tags" {
  type    = map(string)
  default = {}
}

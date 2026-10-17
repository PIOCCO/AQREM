variable "subscription_id" {
  type = string
}

variable "tenant_id" {
  type = string
}

variable "location" {
  type    = string
  default = "westeurope"
}

variable "resource_group_name" {
  type    = string
  default = "rg-aqrem-tfstate"
}

variable "storage_account_name" {
  type        = string
  description = "Globally unique, 3-24 lowercase alphanumerics (e.g. staqremtfstate01)."
  validation {
    condition     = can(regex("^[a-z0-9]{3,24}$", var.storage_account_name))
    error_message = "storage_account_name must be 3-24 lowercase letters/digits."
  }
}

variable "replication_type" {
  type        = string
  default     = "ZRS"
  description = "LRS | ZRS | GRS | GZRS. State is small; ZRS survives a zone outage in-region."
}

variable "clients" {
  type        = set(string)
  default     = []
  description = "Dedicated client ids. Each gets its own container tfstate-<client> (separate RBAC scope)."
  validation {
    condition     = alltrue([for c in var.clients : can(regex("^[a-z][a-z0-9-]{2,19}$", c))])
    error_message = "client ids must match ^[a-z][a-z0-9-]{2,19}$ (same rule as scripts/new-client-env.sh)."
  }
}

variable "platform_state_principal_ids" {
  type        = map(string)
  default     = {}
  description = "Named Entra principals (label => object id) with read/write on the platform + shared stacks' state container."
}

variable "client_state_principal_ids" {
  type        = map(map(string))
  default     = {}
  description = "Per client: label => object id of principals allowed to read/write THAT client's state only, e.g. { contoso = { ops-pipeline = \"<oid>\", alice = \"<oid>\" } }."
}

variable "all_clients_principal_ids" {
  type        = map(string)
  default     = {}
  description = "Principals that operate every client (e.g. the rollout pipeline identity). Keep this list short."
}

variable "allowed_ip_cidrs" {
  type        = list(string)
  default     = []
  description = "Optional: operator/CI egress IPs. Non-empty => storage firewall default Deny with these allowed."
}

variable "public_network_access_enabled" {
  type        = bool
  default     = true
  description = "false = private endpoint only (you must then run Terraform from inside the VNet)."
}

variable "soft_delete_days" {
  type    = number
  default = 30
}

variable "tags" {
  type    = map(string)
  default = {}
}

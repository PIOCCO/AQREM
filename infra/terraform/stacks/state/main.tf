# Remote state storage for every AQREM Terraform stack.
#
#   * Entra ID only: shared key (account keys + SAS) disabled; backends use use_azuread_auth = true.
#   * One container per dedicated client (tfstate-<client>) and one for platform/shared stacks
#     (tfstate-platform); "Storage Blob Data Contributor" is granted on the CONTAINER, to named principals.
#   * Encryption at rest (Microsoft-managed keys + infrastructure encryption), TLS 1.2, HTTPS only,
#     no public blob access, blob versioning + soft delete for blobs and containers, delete lock.
#   * Locking: the azurerm backend takes a blob lease on the state blob during writes (native, no table).

locals {
  tags = merge({ purpose = "terraform-state", managed_by = "terraform" }, var.tags)

  platform_assignments = { for label, oid in var.platform_state_principal_ids : "platform/${label}" => {
    container = "tfstate-platform", principal = oid
  } }
  client_assignments = merge([
    for client in var.clients : merge(
      { for label, oid in lookup(var.client_state_principal_ids, client, {}) : "${client}/${label}" => {
        container = "tfstate-${client}", principal = oid
      } },
      { for label, oid in var.all_clients_principal_ids : "${client}/all:${label}" => {
        container = "tfstate-${client}", principal = oid
      } },
    )
  ]...)
  assignments = merge(local.platform_assignments, local.client_assignments)
}

resource "azurerm_resource_group" "state" {
  name     = var.resource_group_name
  location = var.location
  tags     = local.tags
}

resource "azurerm_storage_account" "state" {
  name                     = var.storage_account_name
  resource_group_name      = azurerm_resource_group.state.name
  location                 = azurerm_resource_group.state.location
  account_tier             = "Standard"
  account_replication_type = var.replication_type
  account_kind             = "StorageV2"

  min_tls_version                   = "TLS1_2"
  https_traffic_only_enabled        = true
  shared_access_key_enabled         = false # Entra ID only: no account keys, no SAS
  default_to_oauth_authentication   = true
  allow_nested_items_to_be_public   = false
  infrastructure_encryption_enabled = true # double encryption at rest
  public_network_access_enabled     = var.public_network_access_enabled
  cross_tenant_replication_enabled  = false

  blob_properties {
    versioning_enabled = true
    delete_retention_policy {
      days = var.soft_delete_days
    }
    container_delete_retention_policy {
      days = var.soft_delete_days
    }
  }

  dynamic "network_rules" {
    for_each = length(var.allowed_ip_cidrs) > 0 ? [1] : []
    content {
      default_action = "Deny"
      bypass         = ["AzureServices"]
      ip_rules       = [for c in var.allowed_ip_cidrs : trimsuffix(c, "/32")]
    }
  }

  tags = local.tags

  lifecycle {
    prevent_destroy = true
  }
}

resource "azurerm_management_lock" "state" {
  name       = "tfstate-cannot-delete"
  scope      = azurerm_storage_account.state.id
  lock_level = "CanNotDelete"
  notes      = "Terraform state for all AQREM environments. Remove only with a reviewed change."
}

resource "azurerm_storage_container" "platform" {
  name                  = "tfstate-platform"
  storage_account_id    = azurerm_storage_account.state.id
  container_access_type = "private"
}

resource "azurerm_storage_container" "client" {
  for_each              = var.clients
  name                  = "tfstate-${each.key}"
  storage_account_id    = azurerm_storage_account.state.id
  container_access_type = "private"
}

# Data-plane access is granted per container. Nobody gets account-wide data access from this stack;
# Owner/Contributor on the subscription still allows granting it, so keep those roles few.
resource "azurerm_role_assignment" "state_rw" {
  for_each = local.assignments

  scope                = "${azurerm_storage_account.state.id}/blobServices/default/containers/${each.value.container}"
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = each.value.principal

  depends_on = [azurerm_storage_container.platform, azurerm_storage_container.client]
}

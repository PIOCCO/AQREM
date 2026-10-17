# Ephemeral + write-only: the admin password is never stored in state or plan.
ephemeral "random_password" "admin" {
  count = var.password_auth_enabled ? 1 : 0

  length  = 32
  special = true
}

resource "azurerm_postgresql_flexible_server" "this" {
  name                          = var.server_name
  resource_group_name           = var.resource_group_name
  location                      = var.location
  version                       = var.postgres_version
  sku_name                      = var.sku_name
  storage_mb                    = var.storage_mb
  backup_retention_days         = var.backup_retention_days
  zone                          = var.zone
  delegated_subnet_id           = var.delegated_subnet_id
  private_dns_zone_id           = var.private_dns_zone_id
  public_network_access_enabled = false

  administrator_login               = var.password_auth_enabled ? var.administrator_login : null
  administrator_password_wo         = var.password_auth_enabled ? ephemeral.random_password.admin[0].result : null
  administrator_password_wo_version = var.password_auth_enabled ? var.secrets_version : null

  authentication {
    active_directory_auth_enabled = var.entra_auth_enabled
    password_auth_enabled         = var.password_auth_enabled
    tenant_id                     = var.entra_auth_enabled ? var.tenant_id : null
  }

  dynamic "high_availability" {
    for_each = var.high_availability_mode != null ? [1] : []
    content {
      mode = var.high_availability_mode
    }
  }

  tags = var.tags

  lifecycle {
    precondition {
      condition     = var.delegated_subnet_id != null && var.private_dns_zone_id != null
      error_message = "Control-plane PostgreSQL requires private networking (delegated_subnet_id and private_dns_zone_id)."
    }
  }
}

resource "azurerm_postgresql_flexible_server_active_directory_administrator" "entra_admins" {
  for_each = var.entra_admin_principal_ids

  server_name         = azurerm_postgresql_flexible_server.this.name
  resource_group_name = var.resource_group_name
  tenant_id           = var.tenant_id
  object_id           = each.value.object_id
  principal_name      = each.value.principal_name
  principal_type      = each.value.principal_type
}

resource "azurerm_postgresql_flexible_server_database" "control" {
  name      = var.database_name
  server_id = azurerm_postgresql_flexible_server.this.id
  charset   = "UTF8"
  collation = "en_US.utf8"

  depends_on = [azurerm_postgresql_flexible_server_active_directory_administrator.entra_admins]
}

# Never enable in production — bootstrap-only escape hatch for break-glass.
resource "azurerm_postgresql_flexible_server_firewall_rule" "allow_azure" {
  count = var.password_auth_enabled && var.allow_public_firewall_bootstrap ? 1 : 0

  name             = "AllowAzureServicesBootstrap"
  server_id        = azurerm_postgresql_flexible_server.this.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

resource "azurerm_key_vault_secret" "admin_password" {
  count = var.key_vault_id != null && var.password_auth_enabled ? 1 : 0

  name             = var.key_vault_secret_name
  value_wo         = ephemeral.random_password.admin[0].result
  value_wo_version = var.secrets_version
  key_vault_id     = var.key_vault_id
  content_type     = "application/x-postgresql-password"
  tags             = var.tags
}

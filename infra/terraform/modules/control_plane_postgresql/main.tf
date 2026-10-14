resource "random_password" "admin" {
  length  = 32
  special = true
}

resource "azurerm_postgresql_flexible_server" "this" {
  name                   = var.server_name
  resource_group_name    = var.resource_group_name
  location               = var.location
  version                = var.postgres_version
  administrator_login    = var.administrator_login
  administrator_password = random_password.admin.result
  sku_name               = var.sku_name
  storage_mb             = var.storage_mb
  backup_retention_days  = var.backup_retention_days
  zone                   = var.zone

  public_network_access_enabled = var.public_network_access_enabled

  dynamic "high_availability" {
    for_each = var.high_availability_mode != null ? [1] : []
    content {
      mode = var.high_availability_mode
    }
  }

  tags = var.tags
}

resource "azurerm_postgresql_flexible_server_database" "control" {
  name      = var.database_name
  server_id = azurerm_postgresql_flexible_server.this.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

resource "azurerm_postgresql_flexible_server_firewall_rule" "allow_azure" {
  count = var.public_network_access_enabled ? 1 : 0

  name             = "AllowAzureServices"
  server_id        = azurerm_postgresql_flexible_server.this.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

resource "azurerm_key_vault_secret" "admin_password" {
  count = var.key_vault_id != null ? 1 : 0

  name         = var.key_vault_secret_name
  value        = random_password.admin.result
  key_vault_id = var.key_vault_id
  content_type = "application/x-postgresql-password"
  tags         = var.tags
}

resource "azurerm_key_vault_secret" "connection_string" {
  count = var.key_vault_id != null ? 1 : 0

  name  = var.connection_string_secret_name
  value = "postgresql+psycopg://${var.administrator_login}:${random_password.admin.result}@${azurerm_postgresql_flexible_server.this.fqdn}:5432/${var.database_name}?sslmode=require"
  key_vault_id = var.key_vault_id
  content_type = "application/x-postgresql-connection-string"
  tags         = var.tags
}

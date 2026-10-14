output "server_id" {
  value = azurerm_postgresql_flexible_server.this.id
}

output "server_name" {
  value = azurerm_postgresql_flexible_server.this.name
}

output "fqdn" {
  value = azurerm_postgresql_flexible_server.this.fqdn
}

output "database_name" {
  value = var.database_name
}

output "auth_mode" {
  value = var.password_auth_enabled ? "password+entra" : "entra_only"
}

output "password_secret_name" {
  value = var.key_vault_id != null && var.password_auth_enabled ? var.key_vault_secret_name : null
}

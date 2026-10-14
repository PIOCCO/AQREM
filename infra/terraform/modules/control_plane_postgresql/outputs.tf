output "server_id" {
  value = azurerm_postgresql_flexible_server.this.id
}

output "fqdn" {
  value = azurerm_postgresql_flexible_server.this.fqdn
}

output "database_name" {
  value = var.database_name
}

output "administrator_login" {
  value = var.administrator_login
}

output "password_secret_name" {
  value = var.key_vault_id != null ? var.key_vault_secret_name : null
}

output "connection_string_secret_name" {
  value = var.key_vault_id != null ? var.connection_string_secret_name : null
}

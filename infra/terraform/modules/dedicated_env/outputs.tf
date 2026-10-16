output "public_url" {
  value = "https://${azurerm_container_app.web.ingress[0].fqdn}"
}

output "key_vault_name" {
  value = azurerm_key_vault.this.name
}

output "key_vault_uri" {
  value = azurerm_key_vault.this.vault_uri
}

output "storage_account_name" {
  value = azurerm_storage_account.this.name
}

output "postgresql_fqdn" {
  value = var.db_mode == "new" ? azurerm_postgresql_flexible_server.this[0].fqdn : null
}

output "postgresql_server_name" {
  value = var.db_mode == "new" ? azurerm_postgresql_flexible_server.this[0].name : null
}

output "managed_identity_client_id" {
  value = azurerm_user_assigned_identity.this.client_id
}

output "migration_job_name" {
  value = azurerm_container_app_job.migrate.name
}

output "container_app_names" {
  value = concat([azurerm_container_app.api.name, azurerm_container_app.web.name, azurerm_container_app.redis.name],
  [for a in azurerm_container_app.worker : a.name])
}

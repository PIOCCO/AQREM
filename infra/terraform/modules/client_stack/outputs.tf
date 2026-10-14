output "resource_group_name" {
  value = azurerm_resource_group.client.name
}

output "managed_identity_client_id" {
  value = azurerm_user_assigned_identity.client.client_id
}

output "key_vault_uri" {
  value = azurerm_key_vault.client.vault_uri
}

output "storage_account_name" {
  value = azurerm_storage_account.client.name
}

output "public_url" {
  value = "https://${azurerm_container_app.web.ingress[0].fqdn}"
}

output "web_origin_hostname" {
  value = azurerm_container_app.web.ingress[0].fqdn
}

output "postgresql_fqdn" {
  value = var.db_mode == "managed" ? azurerm_postgresql_flexible_server.tenant[0].fqdn : null
}

output "deployment_status" {
  value = "provisioned"
}

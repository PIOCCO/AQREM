output "gateway_url" {
  value = "https://${azurerm_container_app.gateway.ingress[0].fqdn}"
}

output "identity_principal_id" {
  value = azurerm_user_assigned_identity.gateway.principal_id
}

output "identity_name" {
  value = azurerm_user_assigned_identity.gateway.name
}

output "container_app_environment_id" {
  value = azurerm_container_app_environment.this.id
}

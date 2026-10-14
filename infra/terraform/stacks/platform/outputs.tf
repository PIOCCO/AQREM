output "platform_resource_group_name" {
  value = azurerm_resource_group.platform.name
}

output "container_registry_login_server" {
  value = module.acr.login_server
}

output "platform_key_vault_uri" {
  value = module.platform_key_vault.uri
}

output "log_analytics_workspace_id" {
  value = module.monitoring.log_analytics_workspace_id
}

output "application_insights_id" {
  value = module.monitoring.application_insights_id
}

output "control_plane_postgresql_fqdn" {
  value = module.control_plane_postgresql.fqdn
}

output "control_plane_database_name" {
  value = module.control_plane_postgresql.database_name
}

output "control_plane_postgresql_auth_mode" {
  value = module.control_plane_postgresql.auth_mode
}

output "model_gateway_url" {
  value = var.enable_custom_gateway ? module.model_gateway_custom[0].gateway_url : (var.enable_apim ? module.model_gateway_apim[0].gateway_url : null)
}

output "front_door_profile_id" {
  value = var.deploy_front_door ? module.front_door[0].profile_id : null
}

output "front_door_endpoint_id" {
  value = var.deploy_front_door ? module.front_door[0].endpoint_id : null
}

output "front_door_endpoint_hostname" {
  value = var.deploy_front_door ? module.front_door[0].endpoint_host_name : null
}

output "azure_openai_endpoint" {
  value = var.deploy_openai ? module.openai[0].azure_openai_endpoint : null
}

output "aqrem_platform_llm_env" {
  value = var.deploy_openai ? module.openai[0].aqrem_backend_env : null
}

output "clients_per_cell" {
  value = var.clients_per_cell
}

output "origin_protection_note" {
  value = "Standard Front Door: lock Container Apps ingress to AzureFrontDoor.Backend and validate X-Azure-FDID (see modules/front_door output)."
}

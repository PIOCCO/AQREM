output "resource_group_name" {
  value = azurerm_resource_group.state.name
}

output "storage_account_name" {
  value = azurerm_storage_account.state.name
}

output "containers" {
  description = "Container per client plus tfstate-platform (identifiers only, no secrets)."
  value       = concat([azurerm_storage_container.platform.name], [for c in azurerm_storage_container.client : c.name])
}

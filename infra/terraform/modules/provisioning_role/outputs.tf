output "role_definition_id" {
  value = azurerm_role_definition.provisioner.role_definition_id
}

output "role_definition_resource_id" {
  value = local.role_definition_id
}

output "vnet_id" {
  value = azurerm_virtual_network.platform.id
}

output "subnet_postgresql_id" {
  value = azurerm_subnet.postgresql.id
}

output "subnet_container_apps_id" {
  value = azurerm_subnet.container_apps.id
}

output "subnet_private_endpoints_id" {
  value = azurerm_subnet.private_endpoints.id
}

output "postgresql_private_dns_zone_id" {
  value = azurerm_private_dns_zone.postgresql.id
}

output "key_vault_private_dns_zone_id" {
  value = azurerm_private_dns_zone.key_vault.id
}

output "blob_private_dns_zone_id" {
  value = azurerm_private_dns_zone.blob.id
}

output "nat_gateway_public_ip" {
  value = var.enable_nat_gateway ? azurerm_public_ip.nat[0].ip_address : null
}

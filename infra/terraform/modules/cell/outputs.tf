output "resource_group_name" {
  value = local.rg_name
}

output "container_app_environment_id" {
  value = azurerm_container_app_environment.this.id
}

output "vnet_id" {
  value = azurerm_virtual_network.cell.id
}

output "nat_egress_ip" {
  value = azurerm_public_ip.nat.ip_address
}

output "subnet_private_endpoints_id" {
  value = azurerm_subnet.private_endpoints.id
}

output "subnet_postgresql_id" {
  value = azurerm_subnet.postgresql.id
}

output "max_clients" {
  value = var.max_clients
}

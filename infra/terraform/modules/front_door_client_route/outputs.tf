output "route_id" {
  value = azurerm_cdn_frontdoor_route.client.id
}

output "origin_host_name" {
  value = azurerm_cdn_frontdoor_origin.client_web.host_name
}

output "custom_domain_host" {
  value = var.custom_domain_host
}

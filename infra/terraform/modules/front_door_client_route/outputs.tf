output "custom_domain_id" {
  value = azurerm_cdn_frontdoor_custom_domain.client.id
}

output "route_id" {
  value = azurerm_cdn_frontdoor_route.client.id
}

output "afd_origin_protection_note" {
  value = "Configure Container Apps ingress restriction: service tag AzureFrontDoor.Backend + header X-Azure-FDID = Front Door profile resource GUID."
}
